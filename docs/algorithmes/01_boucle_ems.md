# 01 · Boucle EMS : acquisition, métronome, trames, machine à états

> Sources : `runtime/coordinator.py` (lignes citées entre parenthèses), `runtime/energy_bus.py`, `domain/engine/models.py`, `domain/engine/load_guard.py`, `const.py`.
> Cette page décrit **ce que le code fait**, pas ce qu'il devrait faire. Les écarts sont numérotés `A-xx` et détaillés dans [ANOMALIES.md](ANOMALIES.md).

## 1. Vue d'ensemble

FoxCat n'a **pas d'horloge de décision périodique**. Chaque *publication réelle* du capteur de puissance réseau signée (« le métronome ») ouvre une **trame**. Une trame produit un **instantané** (`EnergySnapshot`) unique, consommé par deux cœurs indépendants :

```text
publication réseau ──► _async_metronome_report ──► _async_metronome_pulse
                                                      │  (1 trame, 1 snapshot)
                              ┌───────────────────────┴───────────────────────┐
                              ▼                                               ▼
                    Onduleur Core (PRI)                              EMS Core (boiler,
                    async_handle_inverter_grid_frame                  comptabilité, délestage)
                                                                      async_handle_house_frame
```

Les deux tâches partent du même snapshot et ne s'attendent jamais. Le **bus d'énergie** (`EnergyBus`) transporte les messages entre cœurs et garde l'historique des trames.

En parallèle, un rafraîchissement `DataUpdateCoordinator` toutes les **30 s** (`update_interval`, l. 428) exécute `_async_update_data` : watchdog, fin de journée solaire, délestage, chauffage, puis reconstruction des données. Ce n'est pas une trame.

## 2. Le métronome (fraîcheur de la mesure réseau)

Le métronome est un **chien de garde de fraîcheur**, pas une horloge. Deux capteurs : **principal** (puissance réseau signée) et **secours** (facultatif).

Réglages (appareil Système, valeurs par défaut) :

| Réglage | Défaut | Plancher appliqué |
|---|---|---|
| `metronome_period_s` | 30 s | 10 s |
| `metronome_primary_timeout_s` | 45 s | au moins la période |
| `metronome_fallback_timeout_s` | 90 s | au moins le délai du principal |

### 2.1 Fraîcheur d'un capteur (`_metronome_entity_fresh`, l. 919)

Un capteur est frais si son état n'est pas `unknown/unavailable/none/""` **et** si `now − last_reported ≤ délai`. L'instant de référence est `last_reported` (publication réelle, même sans changement de valeur) ou, à défaut, `last_updated` (l. 908).

### 2.2 Réception d'une publication (`_async_metronome_report`, l. 1055)

Sous le verrou `_metronome_lock` :

1. Ignorer si l'instant de publication n'est pas strictement plus récent que le dernier vu pour ce capteur (anti-doublon).
2. Identifier la source : principal ou secours (sinon, ignorer).
3. Compter la publication.
4. **Rejeter** une publication trop ancienne (âge > délai de sa source) : le principal attend le secours, le secours est rejeté.
5. Si la source est le **secours alors que le principal est frais** : enregistrer « principal toujours souverain » et **ne pas** déclencher de trame.
6. Sinon, **libérer le verrou** puis lancer `_async_metronome_pulse`.

### 2.3 Chien de garde (`_async_metronome_watchdog`, l. 993)

Appelé à chaque rafraîchissement de 30 s :

1. Si la date locale a changé : remise à zéro journalière (§ 6).
2. Clôturer en `TIMEOUT` toute trame `PENDING` depuis plus de **10 s**.
3. Pour chaque capteur, rattraper une publication manquée (si `last_reported` est plus récent que le dernier vu, la traiter avec l'origine `watchdog`).
4. Évaluer l'état :

| Principal frais | Secours frais | État | Source | Effet |
|---|---|---|---|---|
| non | oui | `FALLBACK` | `SECOURS` | seule une vraie publication du secours déclenche une trame |
| oui | — | `SYNCHRONISE` | `PRINCIPAL` | aucune trame synthétique |
| non | non | `PERDU` | `AUCUNE` | `pri_state.guard_reason = metronome_perdu` ; plus aucune trame, donc EMS et PRI gelés par absence de mesure |

### 2.4 Voie historique

Sans capteur de métronome configuré, une publication du capteur réseau signé (ou des anciens capteurs export/legacy) déclenche quand même une trame `legacy_event` (`_on_grid_event`, l. 1184). Avec un métronome configuré, les événements réseau ne font que **rafraîchir les données** sans créer de trame.

## 3. Construction de l'instantané (`snapshot`, l. 1517)

### 3.1 Source de la puissance réseau

```text
si secours configuré ET frais ET (source courante = SECOURS OU principal non frais) → secours
sinon                                                                              → principal
```

### 3.2 Calculs

Notation : `pv ≥ 0`, `raw` = puissance réseau lue.

| Convention | Prélèvement `imp` | Réinjection `export` |
|---|---|---|
| + prélèvement / − réinjection (défaut) | `max(raw, 0)` | `max(−raw, 0)` |
| + réinjection / − prélèvement | `max(−raw, 0)` | `max(raw, 0)` |

```text
maison     = max(pv + imp − export, 0)          (conservation de la puissance au point de raccordement)
grid_net_w = export − imp                        (convention interne : + réinjection / − prélèvement)
```

`valid` est vrai seulement si le capteur PV et le capteur réseau actif ont une valeur numérique **et** si le capteur réseau actif est frais. Une valeur illisible vaut `0` pour le calcul mais rend le snapshot invalide.

Pour les installations antérieures à la 1.6 (sans capteur signé), le snapshot lit maison, export et import séparément ; `valid` exige les quatre capteurs.

### 3.3 Boiler et divers

| Champ | Calcul |
|---|---|
| `boiler_power_w` | `max(puissance lue, 0)` |
| `boiler_on` | capteur binaire ON **ou** puissance **> 200 W** (seuil codé en dur) |
| `boiler_temp_c` | sonde de référence (0 si illisible) |
| `boiler_safety_temp_c` | sonde de résistance si valide, sinon sonde de référence |
| `boiler_setpoint_c` | attribut `temperature` du climate, sinon `boiler_temp_normal_c` |
| `machine_active` | au moins une machine pilotable dont l'entité de cycle est ON |
| `inverter_power_w` | puissance live de l'onduleur (informatif, ne cadence rien) |

> **Limite** : `maison = pv + import − export` suppose qu'aucune batterie ne passe entre la production et le compteur. Avec une batterie hybride, « pv » doit être la puissance totale de l'onduleur.

## 4. Pulsation et dispatch (`_async_metronome_pulse`, l. 1106)

Sous `_frame_dispatch_lock` :

1. Mise à jour de l'état du métronome (statut, source, compteur de battements).
2. `_frame_id += 1`, `_frame_serial += 1`, **un seul** `snapshot()`.
3. Enregistrement passif pour l'apprentissage des machines.
4. Ouverture de la trame dans le bus (`on_grid_frame`).
5. Création de deux tâches Home Assistant : cœur **ONDULEUR** puis cœur **EMS**, chacune enveloppée par `_run_dispatched_core`, qui marque la trame `ERROR`/`CANCELLED` pour ce cœur si une exception survient (aucune trame ne reste `PENDING` sur erreur).

`frame_id` repart de 0 chaque jour ; `frame_serial` est cumulatif (ACK N+1 du PRI).

## 5. EMS Core (`async_handle_house_frame`, l. 2665)

Sous `_core_lock`, dans l'ordre :

1. **Acquittement des messages** du bus destinés à EMS (reçus sur cette trame).
2. **Snapshot invalide** → `_sensor_reset_active = True`, compteur de stabilisation à 0, décisions EMS gelées, messages marqués `NOK`, trame `NOK`. PRI, ACK et délestage sont **conservés**.
3. **Reprise après invalidité** : il faut **2 trames valides** ; la première sert uniquement de *stabilisation* (aucune décision, trame `STABILISATION`) ; à la seconde, `reset_core("Capteurs stabilisés…")` et reprise normale.
4. **Comptabilité** (toujours, même régulation coupée) : appareils (machines + chauffe-eau « géré » si la régulation est active), batterie/VE virtuels, comptabilité énergie/€ et série quart d'heure (voir `06_comptabilite.md`).
5. **Si `regulation_active`** : `_evaluate_high_load` (délestage) puis `_core_process_frame`. Sinon : « télémétrie seulement », `guard_reason = regulation_inactive`.
6. Acquittement `traité`, publication du message `CORE_DECISION` vers l'onduleur, trame `PROCESSED`.

## 6. Remise à zéro journalière (l. 937, `energy_bus.reset_daily_counters`)

Au premier battement du watchdog d'un nouveau jour local (ou à minuit) : archivage des compteurs de la veille (battements, publications principal/secours, trames, messages), puis `pulse_count`, compteurs de publication et `frame_id` à 0 ; les messages du bus encore `WAIT_ACK` passent en `TIMEOUT`, puis l'historique des messages et des trames est vidé.

## 7. Machine à états de l'EMS Core (`_core_process_frame`, l. 2826)

États : `ACQUISITION` → `DECISION` → `WAIT_ACK` → `ACQUISITION`. Toute phase inconnue ramène à `ACQUISITION` (`_set_core_phase`, l. 2362) ; le watchdog (l. 3992) réinitialise aussi.

### 7.1 Garde-fous évalués à chaque trame, avant la phase

| # | Condition | Action |
|---|---|---|
| 1 | snapshot invalide | `reset_core` |
| 2 | délestage actif, mode ≠ Manuel, « couper le boiler » activé | boiler allumé → **arrêt** (origine `DELESTAGE`) ; sinon `reset_core` ; **retour** |
| 3 | boiler allumé et sonde de sécurité ≥ `boiler_temp_safety_c` (68 °C) | **arrêt** (origine `SECURITE`) ; retour. Actif **dans tous les modes** |
| 4 | mode ≠ Manuel, boiler allumé, machine protégée en cycle, et surplus insuffisant (voir § 7.4) | **arrêt** (origine `MACHINE`) ; retour |

### 7.2 Phases

- **ACQUISITION** : mémoriser le snapshot comme **T0**, passer en `DECISION`, ACK `IDLE`. Aucune décision sur cette trame.
- **WAIT_ACK** : si la commande physique est `QUEUED` ou `EXECUTION`, enregistrer la trame sans bloquer. Sinon `_validate_core_ack` (§ 7.5), nouveau T0, retour en `ACQUISITION`.
- **DECISION** : voir § 7.3.

### 7.3 Décision

1. Si `|grid_net(now) − grid_net(T0)| > stability_tolerance_w` (500 W) : `reset_core` — la mesure n'est pas stable entre deux trames, aucune décision.
2. Choix de l'**intention boiler** (`BoilerIntent` = action + raison + origine), par priorité :

| Priorité | Cas | Intention |
|---|---|---|
| 1 | délestage actif et « couper le boiler » | ARRÊT (origine `PEAK_SHAVING`) |
| 2 | override utilisateur **FORCE_ON** | `CHAUFFE_45`, sauf si sonde de sécurité ≥ seuil (alors ARRÊT) |
| 3 | override utilisateur **FORCE_OFF** | ARRÊT |
| 4 | **V2H** actif | ARRÊT (interverrouillage, origine `V2H_INTERLOCK`) |
| 5 | mode **Manuel** | `reset_core` : rien |
| 6 | sinon | `evaluate_mode(...)` (voir `02_boiler_et_modes.md`) ; puis, si le tarif est dynamique, `evaluate_dynamic_boiler_v2` **remplace** l'intention |

3. **Machine protégée** : si l'intention n'est pas utilisateur, démarre/maintient le boiler, que la politique réseau **n'est pas** « Compensation » et qu'une machine est active, le boiler attend tant que `protected_cycle_boiler_allowed_stable` est faux (surplus sur **les deux trames** T0 et maintenant).
4. **Politique Compensation** : si l'intention est ARRÊT, boiler allumé, et que la raison contient `achat réseau` ou `hp`, l'intention devient `AUCUNE` (le réseau sert de tampon). Les sécurités ne sont pas concernées (elles sont traitées avant).
5. Enregistrer demande/origine/raison, puis :
   - `AUCUNE` → `reset_core` ;
   - ARRÊT alors que le boiler est déjà arrêté → `reset_core` ;
   - CHAUFFE_45 / BOOST_65 alors que le boiler est allumé avec une consigne déjà à ±0,6 °C de la cible → `reset_core` ;
   - sinon → `async_command_boiler`.

### 7.4 Machine protégée et boiler (`load_guard.py`)

```text
surplus_avant_boiler = max(grid_net_w + (boiler_power_w si boiler allumé), 0)
boiler autorisé      = pas de machine active  OU  surplus_avant_boiler ≥ boiler_power_w
version « stable »   = T0 avait déjà la machine active ET la condition tient sur T0 et sur la trame courante
```

Si la machine vient de démarrer entre T0 et la trame courante, le boiler n'est **pas** autorisé tant qu'une nouvelle acquisition n'a pas confirmé (aucune décision sur un échantillon antérieur à la machine).

### 7.5 Validation de l'ACK (`_validate_core_ack`, l. 3010)

Après une commande boiler, la trame suivante compare le réseau mesuré à l'attendu :

```text
erreur   = |grid_net_w − grid_expected|
direction OK :
  arrêt       → grid_net_w ≥ référence + delta × 0,5
  mise en marche → grid_net_w ≤ référence − delta × 0,5
  passage à 65 °C (déjà allumé) → boiler allumé et consigne ≥ boost − 1
ACK OK  ⇔  erreur ≤ ack_tolerance_w (400 W)  OU  direction OK
```

Un ACK **NOK** est consigné (raison, `ack_error`) mais ne déclenche **aucune correction** automatique (voir A-06).

## 8. Commande du boiler

### 8.1 `async_command_boiler` (l. 3053)

1. Refusée si la régulation est inactive, sauf origines `UTILISATEUR` et `SECURITE`.
2. Refusée (statut `FAILED`) si aucun climate n'est configuré.
3. Prépare l'attendu : `référence = grid_net_w` ; `delta = max(puissance mesurée, boiler_power_w)` à l'arrêt, `boiler_power_w` au démarrage, `0` pour une montée à 65 °C déjà en marche ; `attendu = référence ± delta`.
4. Publie l'intention sur le bus, passe en `WAIT_ACK`, statut d'exécution `QUEUED`.
5. **Préempte** toute commande précédente encore en cours, puis lance le worker physique (`_execute_boiler_command`) hors de la tâche de trame.

Noms d'action internes : `BOILER_OFF_STRATEGY`, `BOILER_ON_45`, `ECS_MODULE_ON_65`, `ECS_MODULE_UPGRADE_65`… (les variantes `ECS_MODULE_ON_45` et `BOILER_ON_45_PRICE` dépendent d'anciens modes inatteignables, voir A-02).

### 8.2 Worker physique (`_execute_boiler_command`, l. 3127)

Sous `_ems_action_lock`, chaque appel de service est borné à **3 s** (`_async_ems_service_call`) :

| Action | Appels |
|---|---|
| ARRÊT | `climate.set_hvac_mode(off)` |
| CHAUFFE_45 / BOOST_65 | `climate.set_temperature(45 ou 65 °C)` **puis**, si réussi, `climate.set_hvac_mode(heat)` |

En cas d'échec/timeout : message `BOILER_COMMAND_TIMEOUT` sur le bus et statut `TIMEOUT`/`FAILED`. Sinon statut `SENT`, horodatage (sert au délai PRI/boiler), et lancement du vérificateur.

### 8.3 Vérification (`_verify_boiler_execution`, l. 3165)

Jusqu'à **4 contrôles** (à +8 s, puis +5 s, +5 s, +5 s) :

```text
logique OK  : climate = off (arrêt) ou heat (marche) ; pour un boost, consigne ≥ boost − 1
physique OK : boiler arrêté (arrêt) ou allumé (marche)   [binaire ou puissance > 200 W]
```

- OK → statut `OK`.
- 4ᵉ échec → `FAILED` « non exécutée après 3 tentatives ».
- Sinon si `_execution_blocked` → `BLOCKED` ; sinon `RETRY` et renvoi de la commande.

`_execution_blocked` (marche uniquement) : fonction boiler ou appareil boiler désactivé, ou sécurité thermique atteinte ; hors `FORCE_ON` : machine protégée sans surplus ; mode Manuel.

### 8.4 Surveillance de sécurité (`async_handle_safety_change`, l. 3256)

Déclenchée par un changement des capteurs de sécurité (puissance/température boiler…) : arrêt immédiat si sécurité thermique dépassée (même régulation coupée ou override actif) ; sinon, régulation active : arrêt si machine protégée sans surplus (override `AUTO`, mode ≠ Manuel) et réconciliation des machines.

## 9. Overrides utilisateur (`async_user_boiler_override`, l. 3662)

| État | Effet |
|---|---|
| `AUTO` | rend la main à l'EMS (`reset_core`) |
| `FORCE_OFF` | arrêt immédiat ; maintenu à chaque trame |
| `FORCE_ON` | refusé (retour à `AUTO`) si boiler désactivé ou sécurité atteinte ; sinon `CHAUFFE_45` immédiat |

Aucun délai d'expiration : un override reste actif jusqu'à retour manuel à `AUTO` (ou redémarrage : l'état est en mémoire).

## 10. Événements annexes qui touchent la boucle

| Événement | Effet |
|---|---|
| Changement de mode (`async_set_mode`) | `reset_core`, puis réconciliation des machines si la régulation est active (hors Manuel) |
| Changement de régime tarifaire | `reset_core` (nouvelle acquisition) |
| Frontière HP/HC (`_on_tariff_boundary`) | `reset_core` |
| Horaire machine (`_on_machine_schedule`) | `async_reconcile_machines` |
| Changement de prix | capture de la sauvegarde de prix ; la réévaluation immédiate dépend de `MODE_DYNAMIC` (inatteignable, A-02) |
| Fin de journée solaire (`_check_end_solar`, l. 3959) | voir `03_pri_onduleur.md` |

## 11. Paramètres de cette page

| Paramètre | Défaut | Rôle |
|---|---|---|
| `stability_tolerance_w` | 500 W | écart maximal du réseau entre T0 et la trame de décision |
| `ack_tolerance_w` | 400 W | erreur maximale tolérée par l'ACK |
| `watchdog_timeout_s` | 120 s | sans trame depuis ce délai, la machine à états est réinitialisée |
| `metronome_period_s` / `…primary_timeout_s` / `…fallback_timeout_s` | 30 / 45 / 90 s | voir § 2 |
| bus : délai d'ACK inter-cœurs | `max(1,5 × période, 45 s)` | message `WAIT_ACK` → `TIMEOUT` |
| bus : trame `PENDING` | 10 s | trame → `TIMEOUT` |
| Appel de service | 3 s | borne de chaque appel `climate.*` |

## 12. Couverture par les tests

Aucun test unitaire ne couvre la boucle (`runtime/coordinator.py` exige Home Assistant). `tests/test_peak_runtime.py` couvre le délestage ; `tests/test_boiler_hc_failback.py` couvre uniquement le module ECS solaire (inatteignable, A-02).
