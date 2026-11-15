# 08 · Protection du raccordement et chauffage

> Sources : `peak_shaving.py`, `grid_load.py`, `runtime/coordinator.py` (`_evaluate_high_load`, `_activate_high_load_shed`, `_grid_voltage`, `_peak_config`, `_grid_load_view`, `_evaluate_heating_boost`, `_async_apply_heating_setpoints`), `heating_boost.py`, `heating_systems.py`.
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

# Partie A · Protection du raccordement (écrêtage de pointe)

## A1. Rôle

Quand la puissance dépasse un seuil proche de la capacité du disjoncteur, FoxCat **délestage** les charges non essentielles, puis les rétablit quand la puissance est durablement redescendue. Le calcul de déclenchement est **purement fondé sur la puissance** (et non sur une intensité mesurée).

Conditions de fonctionnement (`_evaluate_high_load`) :

- la régulation FoxCat est **active** (sinon l'évaluation n'est pas appelée) ;
- « Délestage haute consommation » est activé (`high_load_shed_enabled`) ;
- le mode n'est **pas Manuel** (sinon un délestage actif est levé et le compteur remis à zéro) ;
- le snapshot est valide (sinon l'état de délestage et les compteurs de trames sont **conservés**, jamais assimilés à 0 W).

L'évaluation tourne **à chaque trame de l'EMS Core et aussi à chaque rafraîchissement de 30 s** (`_async_update_data`) : un même niveau de puissance peut donc compter plusieurs « trames » sans nouvelle publication réseau (A-24).

## A2. Configuration (`PeakShavingConfig`)

Toutes les valeurs sont validées et bornées ; une valeur invalide retombe sur le défaut.

| Réglage | Défaut | Borne | Rôle |
|---|---|---|---|
| calibre du disjoncteur (A) | 0 (non renseigné) | 0–1 000 | active le calcul par disjoncteur |
| tension (V) | 230 | 1–1 000 | voir A3 |
| nombre de phases | 1 | 1–3 | multiplie la capacité |
| coefficient de déséquilibre des phases | 1,0 | 1–3 | réduit la capacité vue du total (phases > 1) |
| base de mesure | consommation maison | maison / import réseau | puissance comparée aux seuils |
| seuil de déclenchement | 90 % | 50–100 % | part du disjoncteur |
| seuil absolu de déclenchement | 5 000 W | 1–1 000 000 | utilisé **sans** disjoncteur |
| seuil de réarmement | 0 % (= absolu) | 0–99 % | part du disjoncteur |
| seuil absolu de réarmement | 3 500 W | 0–1 000 000 | utilisé sans disjoncteur ou si le ratio est 0 |
| trames hautes avant déclenchement | 0 (auto) | 0–10 | auto = 1 avec disjoncteur, 2 sans |
| trames basses avant réarmement | 5 | 1–30 | confirmation de retour au calme |
| actions | boiler, machines, onduleur, démarrages flexibles, V2H : toutes activées | — | voir A6 |
| cible V2H | 80 % | 30–100 % | voir 09 |

## A3. Capacité et seuils

```text
capacité utile (W) = calibre × tension × phases ÷ coefficient     (÷ coefficient seulement si phases > 1 ; sinon calibre × tension)
déclenchement      = capacité utile × seuil %                      (sans disjoncteur : seuil absolu)
réarmement         = min( capacité utile × réarmement % si > 0, sinon seuil absolu de réarmement ;  déclenchement × 0,95 )
```

Le réarmement est **toujours au moins 5 % sous le déclenchement** (hystérésis minimale) pour éviter les oscillations.

**Tension utilisée** (`_grid_voltage`) : si des capteurs de tension sont configurés, FoxCat recoupe la tension **phase-neutre** (L1, L2, L3) et la tension **entre lignes** (L1-L2, L2-L3, L3-L1) :

```text
phase seule    → moyenne des tensions de phase
lignes seules  → moyenne des tensions entre lignes ÷ √3
les deux       → (moyenne phase + moyenne lignes ÷ √3) ÷ 2
```

Seules les valeurs plausibles sont retenues (phase : 100–300 V ; lignes : 170–520 V). L'ancien capteur de tension unique est utilisé s'il est le seul (< 300 V = tension de phase, sinon tension entre lignes). Sans mesure : tension nominale (une valeur ≥ 300 V est ramenée à la tension de phase par ÷ √3). La tension de phase obtenue remplace celle du disjoncteur dans le calcul de capacité.

**Coefficient de déséquilibre** : sans courant par phase, la phase la plus chargée est inconnue ; un coefficient K suppose qu'elle porte K fois la charge moyenne. Avec 25 A, 3 phases, 230 V, 90 % : 15 525 W à K = 1 ; **11 942 W à K = 1,3**. Les tensions ne renseignent pas sur la répartition des courants : elles améliorent la précision, le coefficient couvre le déséquilibre.

## A4. Machine à états du délestage (`evaluate_step`)

```text
inactif :
    si mesure ≥ déclenchement : trames hautes + 1, sinon 0
    si trames hautes ≥ N (1 avec disjoncteur, 2 sans, ou valeur configurée) → événement TRIGGER
actif :
    si mesure ≤ réarmement : trames basses + 1, sinon 0
    si trames basses ≥ M (5)  → événement RELEASE
```

Entre les deux, aucun changement. La puissance comparée (`measured_power_w`) est la **consommation maison** ou l'**import réseau** (`max(import, 0)`) ; avec production solaire, l'import évite de délester quand le solaire couvre la charge.

## A5. Déclenchement (`_activate_high_load_shed`)

1. État « actif » avec raison et heure ; `reset_core`.
2. Si l'option est active : message `DELESTAGE_LIBERATION_100` à l'onduleur et **consigne PRI 100 %** (libère l'onduleur).
3. Si l'option « couper le boiler » est active et que le boiler tourne : arrêt (origine `DELESTAGE`).
4. `async_reconcile_machines` : coupe les machines délestables hors cycle (voir 07).

Pendant le délestage, le cœur EMS applique en priorité l'arrêt du boiler (voir 01 § 7.1) et le planificateur interdit tout nouveau démarrage flexible (`peak_shaving_active`).

## A6. Réarmement

À `RELEASE` : état inactif, `reset_core`, réconciliation des machines. Le boiler redémarre selon la stratégie normale à la trame suivante ; aucune action de « restauration » explicite n'est lancée.

## A7. Diagnostic de charge (`grid_load.py`) — informatif

Aucune commande ne dépend de ces valeurs ; elles alimentent les capteurs « Intensité réseau », « Charge du disjoncteur principal » et « Décharge batterie demandée ».

```text
MONO         : I = |P| ÷ (U × cos φ)
TRI / TETRA  : I = max des intensités de phase mesurées, sinon |P| ÷ (√3 × U_composée × cos φ) × coefficient de déséquilibre
charge %     = I ÷ calibre × 100 ; excédent = max(I − calibre × seuil %, 0)
décharge (W) = excédent × U × cos φ (mono) ou excédent × √3 × U_composée × cos φ ÷ coefficient (tri, estimation à partir de la puissance)
```

`U_composée` = U × √3 si la tension mesurée est < 300 V, sinon la tension mesurée. La puissance utilisée est la **consommation maison** (`house_w`) du snapshot. Attributs du capteur de charge : intensité estimée, source, coefficient, tensions utilisées et leur origine, écart entre phases (voir README).

Remarque : ces valeurs utilisent `house_w` alors que le déclenchement utilise la **base de mesure** choisie (maison ou import), ce qui peut les rendre différentes.

## A8. Paramètres sans effet

`high_load_confirm_s` (30 s) et `high_load_restore_s` (120 s) existent comme entités nombre mais ne sont lus nulle part : la confirmation passe par le nombre de trames (A-03).

---

# Partie B · Chauffage : décalage de consigne

## B1. Principe

Fonction **désactivée par défaut**. FoxCat calcule un décalage de consigne (°C) selon le surplus solaire et la présence, le **publie** dans des capteurs, et **n'écrit jamais** dans les thermostats. Une automatisation Home Assistant (voir `docs/automations/etage_decalage_vtherm.yaml`) applique ce décalage aux presets de Versatile Thermostat. L'état (pas accordés, date du dernier changement) reste en mémoire et **repart à 0 au redémarrage** (voulu).

## B2. Évaluation (`heating_boost.evaluate`)

Appelée à chaque rafraîchissement de 30 s (`_async_update_data`). Entrées : régulation active, snapshot valide, export, import, présence, puissance du groupe de climatisation.

**Conditions d'arrêt** (retour immédiat à 0, état remis à zéro), dans l'ordre : fonction désactivée ; régulation inactive ; snapshot invalide ; « uniquement maison vide » actif et présence > 0 ou inconnue (une présence inconnue vaut « présent »).

**Calcul** :

```text
surplus = export + puissance du groupe − réserve                       (le chauffage en cours fait partie du surplus)
désiré  = min( floor(max(surplus, 0) ÷ surplus_par_pas), max_pas )      max_pas = floor(décalage max ÷ pas)
maintien = min(pas actuels, floor(max(surplus, 0) ÷ (surplus_par_pas × 0,60)))
```

| Cas | Résultat |
|---|---|
| désiré > actuel et délai depuis le dernier changement < `hold_s` | augmentation retenue (anti-yoyo) |
| désiré > actuel et puissance du groupe ≥ 90 % de sa limite | augmentation bloquée (garde de puissance) |
| désiré > actuel | augmentation au désiré |
| désiré ≤ actuel et import > `import_max_w` | **baisse immédiate** au désiré |
| sinon | cible = max(désiré, maintien) : un pas accordé est conservé tant que le surplus reste ≥ 60 % de son seuil |

Décalage publié = `pas accordés × pas_c`. Défauts : décalage max 2 °C, pas 0,5 °C (4 pas), surplus par pas 500 W, réserve 100 W, délai 300 s, import max 300 W, limite du groupe 2 500 W, garde à 90 %.

Le décalage « appliqué » aux presets (écrit par l'automatisation) est borné à 0–5 °C ; il est mémorisé et conservé au redémarrage.

## B3. Systèmes de chauffage (pompes à chaleur)

Un **système** = un groupe extérieur (nom, type air/air, eau/eau ou air/eau, capteur de puissance obligatoire, tension et phase facultatifs) ; pour l'air/air, de 0 à **5** unités intérieures (`climate.*`). Validation : nom, type et capteur obligatoires ; au-delà de 5 unités : erreur.

- **Puissance du groupe** (garde) : capteur configuré dans le menu, sinon **somme** des puissances des systèmes.
- **Calcul par système** : chaque système lance sa propre évaluation avec **le même surplus total** (donc le surplus n'est pas réparti entre systèmes, A-25) mais avec sa **propre** garde de puissance et son **propre** anti-yoyo.
- Un capteur par système publie son décalage.

## B4. Optimisation des consignes (air/air, option « FoxCat applique la consigne », défaut non)

Pour chaque système où l'option est active (`plan_system`), toutes les unités reçoivent **la même consigne** tant qu'un décalage est accordé :

```text
référence      = unités que l'utilisateur chauffe lui-même (mode heat avec consigne)
                 (si toutes sont éteintes : consigne d'avant optimisation, ou celle affichée, des unités pouvant chauffer)
consigne commune = moyenne des consignes d'origine des unités de référence + décalage, plafonnée à la température maximale du système (24 °C par défaut, 16–30 °C)
par unité en chauffage : consigne = commune, arrondie au pas de l'unité, jamais en dessous de sa consigne d'origine, bornée par min/max de l'unité
unité éteinte pouvant chauffer : rallumée au niveau commun (mémorise mode et consigne d'origine)
```

Avant la première modification, **mode et consigne d'origine sont mémorisés** (conservés au redémarrage) ; dès que l'optimisation n'est plus possible (décalage 0, fonction ou régulation coupée, option retirée, système supprimé), l'état et la consigne sont **rétablis**.

**Interventions manuelles** : si l'utilisateur éteint une unité que FoxCat avait allumée, ou change son mode pendant la rehausse, FoxCat **n'y touche plus** (suivi « supprimé ») jusqu'à la fin de la rehausse ; si la consigne lue s'écarte de plus de 0,25 °C de la dernière consigne écrite, la nouvelle valeur devient la consigne d'origine.

**Robustesse** : appels `climate.set_hvac_mode` / `set_temperature` bloquants ; en cas d'échec le suivi n'est pas modifié (nouvel essai au cycle suivant) et, si l'unité venait d'être allumée sans consigne acceptée, elle est ré-éteinte.

## B5. Interactions

Le chauffage lit le même surplus que le boiler et les machines, sans coordination avec eux : le boiler absorbe d'abord l'export, ce qui réduit le surplus vu par le chauffage à la trame suivante (comportement émergent, non arbitré).

## B6. Couverture par les tests

`tests/test_peak_shaving.py`, `tests/test_peak_runtime.py` et `tests/test_grid_load.py` couvrent la protection (configuration, seuils, machine à états, tensions, coefficient). `tests/test_heating_boost.py` et `tests/test_heating_systems.py` couvrent la logique pure du chauffage. **Non couverts** : `_evaluate_high_load` avec les trames de la minuterie de 30 s, `_async_apply_heating_setpoints`.
