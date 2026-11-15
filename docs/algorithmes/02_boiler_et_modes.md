# 02 · Boiler et modes EMS

> Sources : `domain/engine/modes/*` (`__init__`, `eco`, `common`, `dynamic_boiler_v2`, `ecs_solar`, `manual`, `zero_injection`), `domain/engine/load_guard.py`, `domain/engine/flexible_boiler.py`, `domain/tariff/tariff.py`, `runtime/coordinator.py` (`_boiler_thermal_view`, `_boiler_on_seconds`).
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

## 1. Ce qui est réellement atteignable

Le réglage `mode` ne peut valoir que **Éco, Confort ou Manuel** (`MODES`) : `async_set_mode` et la migration convertissent tout ancien nom (Dynamique, Bihoraire, Zéro injection, ECS solaire…) vers Éco. Conséquences pour le boiler :

| Module | Atteignable ? | Remarque |
|---|---|---|
| `evaluate_eco` | **oui**, pour Éco **et** Confort | Confort et Éco appliquent exactement le même algorithme boiler |
| `evaluate_manual` | oui | retourne « aucune action » |
| `evaluate_dynamic_boiler_v2` | **oui**, mais seulement via la branche « tarif dynamique » du cœur EMS | remplace l'intention d'Éco/Confort |
| `evaluate_ecs_solar` | **non** | nécessite `mode = Bihoraire` (A-02) |
| `evaluate_zero_injection` | **non** | nécessite `mode = Zéro injection` (A-02) |
| `evaluate_flexible_boiler` | **non**, et **cassé** | n'est importé nulle part ; importe une constante absente de `const.py` (A-02) |
| `_apply_dynamic_boiler_arbitrage` | **non** | méthode jamais appelée (A-02) |

Le document décrit donc d'abord les algorithmes actifs, puis, en annexe, les modules inatteignables, pour mémoire.

## 2. Vocabulaire

| Terme | Valeur | Sens |
|---|---|---|
| Actions (`BoilerIntent.action`) | `CHAUFFE_45`, `BOOST_65`, `ARRET`, `AUCUNE` | cible 45 °C, stockage 65 °C, arrêt, ne rien faire |
| Cibles | `boiler_temp_normal_c` (45), `boiler_temp_boost_c` (65), `boiler_temp_start_c` (43), `boiler_temp_safety_c` (68) | voir README |
| Origine | texte libre (`ECO_SOLAR`, `HC_RESEAU`, `SECURITE`, `UTILISATEUR`, `MACHINE`, `DYNAMIC_*`…) | trace et règles de priorité |
| Couverture | `max(grid_net_w, 0) ÷ boiler_power_w × 100` | part de la puissance du boiler couverte par la réinjection |
| Surplus avant boiler | `max(grid_net_w + puissance boiler si allumé, 0)` | surplus réel hors consommation du boiler |
| HP / HC | plages `tariff_hp_start_1/end_1/start_2/end_2` (07:00–11:00 et 17:00–22:00 par défaut) | `HP` = dans une plage ; `HC` = hors plage |

Hors plage = heures creuses, **quelle que soit la structure tarifaire** (voir A-11).

## 3. Chaîne de décision du boiler

L'ordre complet vit dans `_core_process_frame` (voir `01_boucle_ems.md` § 7). Résumé :

```text
1. sécurité thermique (≥ 68 °C, sonde de résistance en priorité)    → ARRÊT    [tous modes]
2. délestage actif                                                  → ARRÊT
3. machine protégée sans surplus                                    → ARRÊT
4. override utilisateur (FORCE_ON / FORCE_OFF)
5. V2H actif                                                        → ARRÊT
6. mode Manuel                                                      → rien
7. evaluate_mode (Éco/Confort → evaluate_eco)
8. si tarif dynamique : evaluate_dynamic_boiler_v2 remplace l'intention
9. machine protégée (politique ≠ Compensation)                      → attente
10. Compensation : un ARRÊT « énergétique » est ignoré
```

## 4. Algorithme Éco / Confort (`evaluate_eco`)

Entrées : snapshot courant, T0, réglages, heure, durée ON du boiler, demande courante.

`boiler_on_seconds` (`_boiler_on_seconds`, l. 1677) : le binaire est l'horloge de cycle (durée depuis son dernier changement). Si le binaire n'est pas ON mais la puissance dépasse 200 W, la durée est **0** (jamais inventée) ; boiler arrêté → 999 999 s.

Étapes, dans l'ordre (la première qui s'applique gagne) :

| # | Condition | Résultat |
|---|---|---|
| 1 | fonction Boiler désactivée (`boiler_enabled`) | ARRÊT, origine `SECURITE` |
| 2 | sonde de sécurité ≥ `boiler_temp_safety_c` | ARRÊT, `SECURITE` |
| 3 | température de référence ≥ `boiler_temp_boost_c` (65 °C) | ARRÊT, stockage terminé |
| 4 | calcul des couvertures `cov_now` (snapshot) et `cov_t0` ; `solar_full` = les deux ≥ 100 % | — |
| 5 | **HP** et boiler allumé et import > 50 W | ARRÊT : « achat réseau HP interdit » |
| 6 | boiler allumé depuis moins de `boiler_cycle_min_s` (120 s) : < 45 °C → `CHAUFFE_45` ; ou demande courante `BOOST_65` et import ≤ 50 W → `BOOST_65` | cycle minimum respecté |
| 7 | boost engagé (allumé, demande `BOOST_65`, entre 45 et 65 °C) : si import ≤ 50 W et PV > 0 → `BOOST_65`, sinon ARRÊT (« surplus disparu ») | continuité du stockage |
| 8 | `solar_full` : < 45 °C → `CHAUFFE_45` ; < 65 °C → `BOOST_65` | **le surplus est valorisé avant tout bridage PRI** |
| 9 | boiler allumé, < 45 °C : en HC et `boiler_allow_hc` → `CHAUFFE_45` (chauffe HC jusqu'à 45 °C) ; sinon `AUCUNE` (chauffe surveillée) | |
| 10 | HC, `boiler_allow_hc`, boiler arrêté, < `boiler_temp_start_c` (43 °C) : si `hc_grid_start_allowed` → `CHAUFFE_45`, sinon `AUCUNE` (« attente du dernier failback ») | démarrage réseau en HC |
| 11 | boiler allumé et ≥ 45 °C | ARRÊT (« 45 °C atteint sans surplus à stocker ») |
| 12 | sinon | `AUCUNE` (le PRI traitera l'excédent résiduel) |

### 4.1 Dernier failback (`ecs_last_departure`, `hc_grid_start_allowed`)

Si `boiler_hc_wait_failback` est actif (défaut), le démarrage sur le réseau en HC n'est autorisé qu'au **dernier moment utile** :

```text
minutes_avant_HP     = minutes jusqu'au prochain début de HP : avant 07:00 → 07:00 ; entre la fin de HP du matin
                        (11:00) et 17:00 → 17:00 ; à partir de 17:00 → 07:00 du lendemain (bouclage de minuit)
         (pendant HP du matin, 07:00–11:00, la fonction retourne faux ; elle ne distingue pas HP du soir)
température projetée = température actuelle − 0,5 °C × (minutes_avant_HP ÷ 60)     (refroidissement supposé 0,5 °C/h)
minutes_de_chauffe   = max(0, (45 − projetée) ÷ 10 × 60)                             (chauffe supposée 10 °C/h)
failback atteint  ⇔  minutes_avant_HP − minutes_de_chauffe − marge ≤ 0   (marge = boiler_failback_margin_min, 30 min)
```

Les vitesses de refroidissement (0,5 °C/h) et de chauffe (10 °C/h) sont **codées en dur** ; le modèle thermique calculé par FoxCat (volume, puissance) n'est pas utilisé ici (A-08). Option désactivée : démarrage immédiat dès que la HC est ouverte.

### 4.2 Particularités

- **Confort = Éco** pour le boiler. La seule différence entre les deux modes est ailleurs : la réduction de puissance de l'onduleur (PRI) n'est active qu'en Éco (voir `03_pri_onduleur.md`, A-01).
- L'achat sur le réseau n'est jamais autorisé en HP par Éco ; la seule chauffe réseau possible est en HC, bornée à 45 °C (le 65 °C est réservé au solaire).
- En politique **Compensation**, une intention d'ARRÊT « énergétique » (raison contenant `achat réseau` ou `hp`) est neutralisée par le cœur (A-05).

## 5. Boiler en tarif dynamique (`evaluate_dynamic_boiler_v2`)

Appelé **après** `evaluate_mode` quand le tarif est dynamique (source Day-Ahead ou intégration), sauf mode Manuel. Il remplace l'intention d'Éco/Confort, sauf si cette intention a l'origine `SECURITE` ou `UTILISATEUR`.

Entrées : `base_intent`, réglages, et la vue économique (`decision.dynamic_curve_position_pct`, `decision.boiler_charge_now`).

Seuils (valeurs bornées) :

| Réglage | Défaut | Borne appliquée |
|---|---|---|
| zone favorable `dynamic_favorable_position_pct` | 30 % | 5 à 60 % |
| plafond `dynamic_high_position_pct` | 70 % | de la zone favorable à 95 % |
| cible de boost | `min(65 °C, sécurité)` | — |

Ordre d'évaluation :

| # | Condition | Résultat |
|---|---|---|
| 1 | sonde de sécurité ≥ 68 °C | ARRÊT (`DYNAMIC_SECURITE`) |
| 2 | **surplus avant boiler ≥ puissance de la résistance** : < cible de boost → `BOOST_65` (`DYNAMIC_BOOST_SOLAIRE`), sinon ARRÊT/`AUCUNE` | le soleil est souverain ; aucun prix ne bloque ce boost |
| 3 | position Day-Ahead indisponible : si l'intention de base est `BOOST_65` → `CHAUFFE_45` (si < 45 °C) ou ARRÊT/`AUCUNE` ; sinon intention de base inchangée | un boost réseau est interdit même en repli |
| 4 | position **> plafond** | ARRÊT/`AUCUNE` (« Boiler reporté ») |
| 5 | position ≤ zone favorable : < 45 °C → `CHAUFFE_45`, sinon ARRÊT/`AUCUNE` | confort à 45 °C seulement |
| 6 | zone intermédiaire : < `boiler_temp_start_c` (43 °C) → `CHAUFFE_45` (« fallback ECS ») | confort garanti |
| 7 | entre 43 et 45 °C **et** fenêtre Day-Ahead réservée (`boiler_charge_now`) → `CHAUFFE_45` | |
| 8 | ≥ 45 °C → ARRÊT/`AUCUNE` ; sinon attente | |

« ARRÊT/`AUCUNE` » signifie ARRÊT si le boiler est allumé, sinon `AUCUNE`.

Particularité : le réseau ne chauffe **jamais** au-delà de 45 °C ; le stockage à 65 °C n'est possible que sur surplus solaire mesuré.

## 6. Modèle thermique (`_boiler_thermal_view`, l. 1633)

Descriptif seulement ; il ne commande rien. Il alimente la vue économique et le planificateur.

```text
énergie manquante (kWh) = volume (L) × 1,163 × max(cible − mesurée, 0) ÷ 1000        (1,163 Wh par litre et par °C)
durée de chauffe (h)    = énergie manquante ÷ (puissance de la résistance en kW)
capacité de confort     = volume × 1,163 × max(cible − eau froide, 0) ÷ 1000
```

Défauts : volume 250 L, puissance = `boiler_power_w` (1 800 W) ou la valeur configurée, eau froide 15 °C, cible = 45 °C.

## 7. Mode Manuel

`evaluate_manual` ne fait rien. En Manuel, le cœur EMS ne lance aucune stratégie boiler (`reset_core`), mais : la sécurité thermique, le délestage, l'override utilisateur et l'interverrouillage V2H restent actifs ; la commande PRI manuelle n'est acceptée qu'en Manuel.

## 8. Annexe : modules inatteignables (pour mémoire)

### 8.1 ECS solaire (`evaluate_ecs_solar`) — nécessite `mode = Bihoraire`

Stratégie V1.2 : sécurité ; ≥ 65 °C arrêt ; HP avec import → arrêt ; cycle minimum ; puis trois plages selon l'heure.

- **Nuit HC** (de la fin de HP du soir au début de HP du matin), si `boiler_allow_hc` : 22:00–23:00 observation (chauffe seulement au failback) ; 23:00–23:20 charge initiale (si `hc_grid_start_allowed`) ; 23:20–23:50 stabilisation (arrêt, sauf failback critique) ; ensuite continuité/failback.
- **HC jour** : boost solaire 65 °C si couverture ≥ seuil (« agressivité » : `coverage_solar_min_percent` 80 %, `surplus_pv_min_agressivite_w` 300 W, `import_boiler_max_w` 1 200 W), chauffe 45 °C sur couverture stable ≥ 80 %, failback, rattrapage 16:00–17:00.
- **HP** : chauffe maintenue sans import, démarrage à 100 % solaire sur deux trames, arrêt à l'apparition d'un achat.

### 8.2 Zéro injection (`evaluate_zero_injection`)

Retourne toujours `AUCUNE` (« PRI prioritaire »). Le comportement zéro injection est désormais porté par la **politique réseau**.

### 8.3 Charge flexible universelle (`evaluate_flexible_boiler`, V1.7.0)

Version prévue : sécurité → utilisateur → solaire souverain → période de distribution Impact (PIC) → dynamique / bihoraire / fixe, avec un indicateur de confiance de la sonde. **Jamais câblée**, et son import `DISTRIBUTION_WALLONIA_IMPACT` n'existe pas : elle lèverait une erreur si elle était importée.

### 8.4 `thermal_deadline` (`modes/common.py`)

Utilisée uniquement par `modes/dynamic.py` (ancien mode dynamique, non routé).

## 9. Paramètres de cette page

| Entité / réglage | Défaut | Effet |
|---|---|---|
| `boiler_enabled` (Boiler géré par FoxCat) | oui | coupe toute stratégie boiler |
| `boiler_allow_hc` | oui | autorise la chauffe réseau en HC |
| `boiler_hc_wait_failback` | oui | attendre le dernier failback en HC |
| `boiler_failback_margin_min` | 30 min | marge de sécurité du failback |
| `boiler_temp_start_c` / `normal_c` / `boost_c` / `safety_c` | 43 / 45 / 65 / 68 °C | seuils |
| `boiler_cycle_min_s` | 120 s | durée minimale d'un cycle |
| `boiler_power_w` | 1 800 W | puissance nominale (couvertures, surplus, delta ACK) |
| `dynamic_favorable_position_pct` / `dynamic_high_position_pct` | 30 % / 70 % | zones Day-Ahead du boiler dynamique |
| `agressivite_ecs`, `coverage_solar_min_percent`, `surplus_pv_min_agressivite_w`, `import_boiler_max_w` | — | **sans effet** (utilisés seulement par le module inatteignable, A-03) |

## 10. Couverture par les tests

- `tests/test_boiler_hc_failback.py` : démarrage HC avec et sans attente du failback pour `evaluate_eco` (3 cas) et pour `evaluate_ecs_solar` (module inatteignable).
- `tests/test_dynamic_analysis.py` : un appel à `evaluate_mode` (mode Confort).
- **Non couverts** : étapes 5 à 9 et 11 d'`evaluate_eco` (HP, cycle minimum, boost, solar_full), `evaluate_dynamic_boiler_v2`, `ecs_last_departure` en dehors du cas testé, `protected_cycle_boiler_allowed*`.
