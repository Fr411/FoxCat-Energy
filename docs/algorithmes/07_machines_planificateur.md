# 07 · Machines : fenêtres, cycles protégés, apprentissage, planificateur

> Sources : `domain/loads/machines.py`, `machine_cycle.py`, `machine_learning.py`, `flexible_load_planner.py`, `runtime/coordinator.py` (`async_reconcile_machines`, `_tariff_start_favorable`, `machine_states`, `_refresh_machine_cycles`, `async_user_start_machine`, `async_user_stop_machine`, `_record_machine_learning`).
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md). A-22 (panne en tarif dynamique avec un cycle protégé) est **corrigée**.

## 1. Définition d'une machine

| Champ | Défaut | Sens |
|---|---|---|
| `machine_type` | `switch` | `switch` : pilotable par une prise ; `cvc` : observée seulement (nécessite un capteur de puissance) |
| `switch` | — | prise à commander (obligatoire pour `switch`) |
| `cycle` | — | entité « cycle en cours » facultative (ON = cycle externe) |
| `power_sensor`, `current_sensor`, `voltage_sensor` | — | télémétrie ; la puissance sert à détecter et à comptabiliser |
| `phase` | vide | phase du réseau L1/L2/L3 (enregistrée ; **pas encore utilisée** par l'écrêtage) |
| `automatic` | oui | gestion automatique par FoxCat |
| `sheddable` | oui | peut être coupée par le délestage (jamais en plein cycle) |
| fenêtre 1 | 21:30 → 07:00 | plage d'alimentation autorisée |
| fenêtre 2 | 10:30 → 17:00 | seconde plage |
| `cycle_start_w` / `cycle_start_confirm_s` | 10 W / 20 s | seuil et confirmation de démarrage |
| `cycle_duration_minutes` / `cycle_margin_minutes` | 120 / 45 | durée attendue, marge de fin |
| `cycle_end_w` / `cycle_end_confirm_minutes` | 5 W / 10 min | seuil et confirmation de fin |
| `nominal_power_w`, `priority`, `interruptible`, `available_from`, `deadline`, `max_delay_hours` | 2 000 W, 50, non, —, —, 24 h | paramètres du planificateur |

Validation (`machine_from_dict`) : identifiant et nom non vides, type `switch` ou `cvc`, prise pour `switch`, capteur de puissance pour `cvc` ; sinon la machine est ignorée. Les trois machines historiques (lave-linge, sèche-linge, lave-vaisselle) gardent leurs interrupteurs `*_enabled` ; une liste de machines V1.3 (même vide) remplace la lecture historique.

**Fenêtre autorisée** (`machine_allowed`) : l'heure locale est dans la fenêtre 1 **ou** la fenêtre 2 ; une plage qui franchit minuit est acceptée ; début = fin signifie « jamais ».

## 2. Détection et protection des cycles (`MachineCycleManager`)

Une machine n'est jamais coupée en plein programme. Le cycle est un état **logique persistant** : une pause à 0 W ne le termine pas.

États : `IDLE` → `START_DETECTED` → `PROTECTED_CYCLE` → `END_CONFIRMATION` → `FINISHED`. Sont **protégés** : `PROTECTED_CYCLE` et `END_CONFIRMATION`.

| Situation | Transition |
|---|---|
| entité de cycle externe ON et machine non protégée | démarrage immédiat (origine `EXTERNAL_USER`) |
| `IDLE`/`FINISHED`, puissance ≥ `cycle_start_w` | `START_DETECTED`, chrono de confirmation |
| `START_DETECTED` : puissance retombe < seuil | retour `IDLE` |
| `START_DETECTED` : confirmation ≥ `cycle_start_confirm_s` | `PROTECTED_CYCLE` (origine `POWER_DETECTED`), début = premier dépassement |
| `PROTECTED_CYCLE` : `expected_end_at` atteint | `END_CONFIRMATION` |
| `END_CONFIRMATION` : délai de sécurité (`expected_end_at + marge`) dépassé | `FINISHED` |
| `END_CONFIRMATION` : puissance ≤ `cycle_end_w` pendant `cycle_end_confirm_minutes` | `FINISHED` |
| `END_CONFIRMATION` : puissance remonte | chrono de fin remis à zéro |

`expected_end_at = début + durée` ; `timeout_at = expected_end_at + marge` (au moins 1 minute chacun).

Un **démarrage utilisateur** (bouton) crée un cycle protégé immédiat (`USER_BUTTON`), allume la prise (3 s max) et publie un message ; si la commande échoue, le cycle est annulé. Un **arrêt utilisateur** termine le cycle puis coupe la prise.

Les cycles sont rafraîchis à chaque appel de `machine_states`, `async_reconcile_machines` et à chaque mise à jour de la télémétrie.

## 3. Réconciliation des prises (`async_reconcile_machines`)

Appelée par : changement d'horaire de fenêtre, changement de mode, activation d'une gestion machine, changement de prix (conditions voir 05), événement de sécurité, changement de prix économique. **Ne fait rien** si la régulation est inactive ou si le mode est **Manuel** (« handover complet »).

Pour chaque machine ayant une prise :

```text
cycle_actif   = cycle protégé
gestion       = interrupteur de gestion de la machine ET appareil « Machines » actif
autorisée     = dans une fenêtre
tariff_ok     = (délestage actif et plan du planificateur) ou _tariff_start_favorable(machine)
bloc_délestage = délestage actif ET « couper les machines » ET machine délestable ET pas de cycle actif
garder_allumée = délestage actif ET pas de bloc ET prise actuellement ON
doit_être_ON  = cycle_actif OU garder_allumée OU (gestion ET autorisée ET tariff_ok ET pas de bloc)
→ switch.turn_on si doit_être_ON, sinon switch.turn_off   (blocking=False)
```

**Point d'attention** : si la gestion automatique d'une machine est **désactivée** (ou la machine hors fenêtre), `doit_être_ON` est faux hors cycle et la prise reçoit `turn_off` à chaque réconciliation (A-23).

### 3.1 Autorisation tarifaire d'un nouveau démarrage (`_tariff_start_favorable`)

| Cas | Règle |
|---|---|
| optimiseur désactivé, sans planificateur dynamique | dynamique : prix actuel connu, pas supérieur au prix suivant, pas supérieur à la moyenne du jour ; autre : période **HC** |
| contrat dynamique et mode ≠ Manuel, planificateur actif | `allow_start_now` du planificateur pour cette machine |
| sinon, recommandation de la machine | `allow_start` de `recommend_flexible_load` (voir 05) |
| sans machine précise | `decision.flexible_start` du marché |

`machine_states` recalcule la vue économique et ces décisions pour chaque appel (à chaque trame) : coût de calcul élevé mais sans effet fonctionnel.

## 4. Planificateur de charges flexibles (`build_flexible_load_plan`, V1.7.1)

**Seul décideur de `allow_start_now`** pour un contrat dynamique en mode ≠ Manuel. Actif seulement si l'analyseur de prix est actif (donc contrat dynamique) ; sinon il retourne un plan vide « réservé à Dynamique Day-Ahead ».

### 4.1 Ordre de traitement

1. **Écrêtage actif** (`peak_shaving_active`) : toutes les machines → `SAFETY_OVERRIDE`, démarrage interdit ; boiler idem ; fin.
2. Puissance parallèle maximale :

```text
maxp = min(planner_max_parallel_power_w (5 000 W),
           max(planner_grid_import_limit_w (5 000 W) + PV − maison, 100))
```

3. Paramètres selon le mode : **Confort** : pénalité d'attente 0,03 €/h, économie minimale 0,10 €, attente max 6 h ; **Éco** : 0 €/h, 0,03 €, 24 h.
4. Machines triées par **priorité décroissante**. Pour chacune :
   - gestion automatique désactivée → `USER_CONTROL` ;
   - cycle protégé → `CONTINUE` (autorisé) et réservation de sa puissance jusqu'à la fin prévue ;
   - sinon profil : durée apprise (10 cycles) ≥ 0,25 h sinon durée configurée ; puissance = énergie apprise ÷ durée sinon `nominal_power_w`.
5. **Candidats de départ** : début de chaque point de prix dans la plage `[disponible dès, échéance − durée]` **et** dans une fenêtre de la machine ; plus l'instant « disponible dès » lui-même. Échéance = `deadline` configurée (ou +24 h) bornée par l'attente max du mode.
6. Un candidat est écarté s'il dépasse `maxp` avec les réservations déjà faites (chevauchement).
7. Coût d'un candidat = Σ (prix × puissance ÷ 1000 × pas) sur la durée, + attente × pénalité. Pour un départ « maintenant », la part couverte par le surplus mesuré (`export_w` ÷ puissance de la machine, au plus 1) est chiffrée à la **valeur de réinjection** (négative quand l'injection est pénalisée) au lieu du prix réseau ; sans prix de réinjection connu, le prix réseau reste utilisé.
8. Décision : meilleur candidat = coût minimal ; « maintenant » = candidat dans ±30 pas ; **`START_NOW`** si le meilleur départ est dans moins d'un demi-pas (≥ 5 min) **ou** si l'économie du report est inférieure au minimum ; sinon **`WAIT`** avec heure planifiée. En mode Manuel : `USER_CONTROL`, recommandation seule. Aucun créneau réalisable : `WAIT`.
9. La machine réserve son créneau pour les suivantes.

### 4.2 Boiler dans le planificateur

Sécurité (≥ 68 °C) → `SAFETY_OVERRIDE` ; override utilisateur → `USER_CONTROL` ; besoin thermique nul → `STOP_WHEN_SAFE` ; **nécessité** si température < `boiler_necessity_temp_c` (38 °C) → démarrage obligatoire ; sinon réserve les `n` pas les moins chers (n = durée de chauffe ÷ pas) et démarre si l'instant courant est dans l'un d'eux.

> Cette sortie « boiler » est **informative** : la décision réelle du boiler vient de `evaluate_dynamic_boiler_v2` (voir 02).

## 5. Apprentissage passif (`MachineLearningRecorder`)

Observe à chaque trame réseau et à chaque télémétrie machine, **sans jamais influencer** l'EMS, le PRI ni les cycles.

- Un enregistrement commence quand `cycle_protected` ou puissance ≥ max(seuil de démarrage, 0,5 W) ; il se termine quand la puissance reste ≤ seuil de fin pendant au moins max(délai configuré, 30 s) **et** que le cycle n'est plus protégé.
- Énergie intégrée au **trapèze** `(P_précédente + P) ÷ 2 × dt` ; intervalles > 1 h ignorés.
- Points échantillonnés au plus toutes les 10 s, 720 points par cycle ; **30 cycles** conservés par machine ; sauvegarde au plus toutes les 5 min.
- À la restauration, un cycle en cours **n'est pas repris** (le temps d'arrêt ne devient pas de l'énergie).
- Moyennes sur les 10 derniers cycles : `average_duration_s_10` et `average_energy_wh_10`, utilisées par les planificateurs.

Contexte enregistré avec chaque cycle : réseau, PV, maison, prix actif, période tarifaire.

## 6. Paramètres de cette page

| Réglage | Défaut | Rôle |
|---|---|---|
| `planner_max_parallel_power_w` / `planner_grid_import_limit_w` | 5 000 / 5 000 W | enveloppe de puissance |
| `eco_*` / `comfort_*` : `wait_penalty_eur_h`, `min_saving_eur`, `max_wait_h` | 0 / 0,03 / 24 ; 0,03 / 0,10 / 6 | arbitrage attente vs coût |
| `boiler_necessity_temp_c` | 38 °C | seuil de nécessité du boiler |
| Fenêtres, seuils et durées de cycle | voir § 1 | par machine |
| `device_machines_enabled` | oui | interrupteur global « Machines » |

## 7. Couverture par les tests

`tests/test_vpp.py` importe le planificateur et l'apprentissage ; `tests/test_peak_runtime.py` couvre le délestage des machines. **Non couverts** : le gestionnaire de cycles, la réconciliation des prises, et surtout `build_flexible_load_plan` avec un cycle protégé issu de `MachineCycleManager.snapshot` (A-22).

## 6. Planificateur dynamique (`build_dynamic_plan`)

> Source : `domain/pricing/dynamic_planner.py`, tests `tests/test_dynamic_planner.py`. Capteur « Planificateur dynamique », interrupteur « Planificateur dynamique pilote les machines » (désactivé par défaut), réglage « stabilité du plan ».

Calculé à chaque trame en **tarif dynamique** ; sans l'interrupteur, il reste en **observation** (aucune commande). Avec l'interrupteur (et mode ≠ Manuel), son plan des machines remplace celui du planificateur de charges flexibles (§4) dans `_economic_view`.

1. **Créneaux** : la courbe (15 min ou 1 h) est découpée en créneaux, classés par **rang** de prix : négatif (prix < 0), `TRES_BAS` ≤ 15 %, `BAS` ≤ 35 %, `NORMAL` ≤ 70 %, `ELEVE` ≤ 90 %, `PIC`. Horizon : fin de la courbe, 36 h au plus.
2. **Candidats** (machine non interruptible) : maintenant, chaque début de créneau et chaque ouverture de plage, à condition que **le cycle entier** tienne dans une plage utilisateur, entre « disponible dès » et l'échéance (réglée, bornée par l'attente maximale du mode), sans dépasser la puissance parallèle maximale déjà réservée par les machines plus prioritaires.
3. **Coût** = prix moyen pondéré sur la durée × puissance × durée, avec une part solaire valorisée à la valeur de réinjection (0 si inconnue) : surplus mesuré pour un départ immédiat, fenêtre de prévision solaire × confiance × 50 % au plus pour un départ futur.
4. **Décision** : coût + attente × pénalité du mode. `START_NOW` si prix négatif, si le meilleur créneau est maintenant, ou si attendre économise moins que l'économie minimale du mode ; sinon `WAIT` avec `planned_start`.
5. **Stabilité** : le départ planifié au calcul précédent est conservé s'il reste à moins de `max(0,005 €, stabilité % du coût)` du meilleur.
6. **Interruptibles** : les créneaux les moins chers (dans les plages, avant l'échéance), dans le désordre ; départ si l'instant courant est dans l'un d'eux.
7. **Sécurités** : cycle protégé → `CONTINUE` ; écrêtage → `SAFETY_OVERRIDE` ; gestion automatique coupée ou mode Manuel → `USER_CONTROL` ; courbe absente → `ATTENTE_PRIX`.

**Machine Learning dans le planificateur.** La durée et la puissance moyenne viennent des 10 derniers cycles appris, à partir de 3 cycles mesurés (sinon réglages). La **forme de consommation** (12 tranches, part d'énergie par tranche, `profile_shape_10`) pondère le coût : chaque tranche est payée au prix de son créneau, ce qui place les pics de la machine (chauffe, essorage) sur les créneaux les moins chers. Attributs exposés : `energy_kwh`, `energy_source`, `learning_cycles`, `profile`.

Hypothèses à connaître : la part solaire future est une estimation prudente, pas une prévision de puissance ; le boiler n'est pas planifié ici.

## 7. Planificateur bi-horaire (`build_bihoraire_plan`)

> Source : `domain/pricing/bihoraire_planner.py` (s'appuie sur `dynamic_planner.py`), tests `tests/test_bihoraire_planner.py`. Capteur « Planificateur bi-horaire », interrupteur « Planificateur bi-horaire pilote les machines » (désactivé par défaut).

Actif seulement en tarif **bi-horaire** (structure HP/HC, hors dynamique). Il construit une courbe de prix de 36 h au quart d'heure (prix HP/HC finaux, compléments inclus) selon les plages HP réglées, puis applique les règles du §6 avec des bandes `HP` / `HC` au lieu des rangs de prix.

- Un cycle est placé **entièrement** dans une plage utilisateur ; ses minutes en HP sont payées au prix HP, donc un départ tardif en HC qui déborde sur les HP perd face à la HC suivante.
- Report seulement si l'économie dépasse le minimum du mode ; HP ≈ HC : démarrage immédiat.
- En observation, rien n'est commandé. Piloté (interrupteur actif, mode ≠ Manuel), son `allow_start_now` remplace la recommandation habituelle (« HC seulement » ou comparateur économique) pour les nouveaux départs.
- Non couvert : jours de semaine / week-end différents, boiler (voir 02).
