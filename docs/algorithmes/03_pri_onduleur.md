# 03 · Onduleur : réduction de puissance PRI / RRCR

> Sources : `runtime/inverter_core.py` (décision), `runtime/coordinator.py` (`_run_pri_frame`, `_pri_actuator_loop`, `_apply_rrcr_level`, ACK, fin de journée solaire, garde), `const.py` (table RRCR), `domain/engine/pri.py` (ancien moteur).
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

## 1. Principe

Le **PRI** limite la puissance de l'onduleur par paliers de **10 %** (0 à 100 %) grâce à quatre relais **RRCR** (L1 à L4). L'**Onduleur Core** décide **à chaque trame** du niveau cible ; un **worker** indépendant applique la dernière consigne demandée, sans jamais retarder les trames suivantes.

```text
trame ──► _run_pri_frame ──► InverterCore.decide ──► cible
                                    │ cible ≠ niveau actuel
                                    ▼
                         _queue_pri_target ──► _pri_actuator_loop ──► 4 × switch.turn_on/off
                                                                       ──► attente du code RRCR (5 s)
trame N+1 ──► _validate_pending_pri_on_frame  (ACK rrcr / onduleur / réseau)
```

## 2. Table RRCR (`RRCR_LEVEL_TO_CODE`)

Le code est lu dans l'ordre **L4 L3 L2 L1** (`_rrcr_code`) ; chaque relais doit être `on`/`off`, sinon le code vaut `????` et le niveau `−1` (« RRCR inconnu », aucune décision).

| Niveau | Code L4L3L2L1 | | Niveau | Code |
|---|---|---|---|---|
| 100 % | `0000` | | 40 % | `0100` |
| 90 % | `1001` | | 30 % | `0011` |
| 80 % | `1000` | | 20 % | `0010` |
| 70 % | `0111` | | 10 % | `0001` |
| 60 % | `0110` | | 0 % | `1010` |
| 50 % | `0101` | | | |

## 3. Garde d'exécution (`_pri_guard`, l. 4038)

Le moteur ne tourne que si **toutes** ces conditions sont vraies, sinon la trame retourne `GARDE_PRI_ACTIVE` et le niveau est **conservé tel quel** :

| Condition | `guard_reason` si fausse |
|---|---|
| `regulation_active` | `regulation_inactive` |
| `pri_enabled` (« Réduction de puissance onduleur ») | `reduction_onduleur_desactivee` |
| mode ≠ **Manuel** (`pri_mode_allowed`) : Éco et Confort | `mode_Manuel` |

*Corrigé (A-01)* : la garde exigeait un mode parmi Éco, « Zéro injection », « Dynamique » ; comme le mode ne vaut plus que Éco, Confort ou Manuel, Confort était exclu à tort (réinjection non limitée). En passant en **Manuel**, le coordinateur libère maintenant l'onduleur à 100 % si le PRI est activé et que le niveau lu est inférieur.

Autres conditions de trame : snapshot invalide → `SNAPSHOT_INVALIDE` (niveau conservé) ; code RRCR illisible → `RRCR_INCONNU`.

## 4. Décision (`InverterCore.decide`)

### 4.1 Entrées et grandeurs dérivées

| Grandeur | Calcul |
|---|---|
| `inverter_w` | `inverter_power_w` (défaut **4 000 W**, minimum 1) |
| plafond actuel | `inverter_w × niveau ÷ 100` |
| `pv_at_limit` | niveau > 0 et (`pv ≥ plafond − tolérance` ou `pv ÷ plafond ≥ 0,92`) ; tolérance = `pri_pv_compare_tolerance_w` (200 W), ratio = `pri_ceiling_ratio` (0,92, borné 0,5–1) |
| `more_possible` | niveau < 100 et `pv_at_limit` |

### 4.2 Règle 1 : politique « Compensation »

Cible = **100 %**, toujours. Le réseau sert de tampon, aucun calcul d'injection ne bride l'onduleur. (C'est le comportement par défaut : le PRI ne bride rien tant que la politique reste Compensation.)

### 4.3 Règle 2 : export rémunérateur

Si la valeur d'export `prices()["export_value"]` est **strictement positive**, cible = **100 %** (« FoxCat ne détruit jamais une production qui a une valeur »). Cette règle n'est pas désactivée par le réglage prédictif.

`export_value` selon la politique réseau (`prices`, l. 1694) :

| Politique | `export_value` |
|---|---|
| Injection non valorisée, Zéro injection | `0` (la règle 2 ne s'applique jamais) |
| Injection tarifée, Compensation | prix dynamique de réinjection (tarif dynamique) ou prix fixe de réinjection (sinon, défaut 0) |

### 4.4 Règle 3 : choix prédictif du palier (toutes les autres situations)

Politiques concernées : **Injection tarifée** (avec valeur ≤ 0), **Injection non valorisée**, **Zéro injection**. Ces trois politiques utilisent **le même algorithme** (A-09).

Paramètres :

| Réglage | Défaut | Rôle |
|---|---|---|
| `network_billed_import_target_w` | 100 W | import cible (un léger import est voulu) |
| `network_billed_import_max_w` | 250 W | import « haut » (au-delà : pénalité ×4, et libération autorisée) |
| `network_billed_export_max_w` | 50 W | réinjection maximale tolérée (au-delà : pénalité ×4) |
| `pri_weight_import` / `pri_weight_export` | 1,0 / 2,0 | poids du score (la réinjection pèse double) |
| `pri_score_margin` | 25 | gain de score minimal pour changer de palier |

**Estimation de la maison** (bilan sur la même trame) :

```text
maison_estimée = max(pv + import − export, 0)
pv_cible       = max(maison_estimée − import_cible, 0)
repère_maison  = niveau le plus proche de pv_cible ÷ inverter_w (arrondi à 10 %)     → diagnostic seulement
```

**Score réseau** (plus petit = meilleur), pour un import `I` et une réinjection `E` prévus :

```text
score = |I − import_cible| × w_import + E × w_export
        + (I − import_max) × w_import × 4   si I > import_max
        + (E − export_max) × w_export × 4   si E > export_max
```

**Simulation des 11 paliers** (0, 10 … 100 %). Pour chaque palier `p` de plafond `Lp` :

| Cas | PV prédit |
|---|---|
| `p` = niveau actuel | `pv` mesuré |
| `p` < actuel | `min(pv, Lp)` |
| `p` > actuel et **PV plafonné** | `Lp` (potentiel inconnu : on suppose que le plafond sera rempli) |
| `p` > actuel et PV non plafonné | `min(pv, Lp)` (monter n'apporte rien) |

« PV plafonné » = `pv_at_limit` **ou** niveau = 0 **ou** import > import « haut ». Ensuite :

```text
réseau_prévu = PV prédit − maison_estimée        (≥ 0 : réinjection ; < 0 : import)
```

**Sélection** : palier de score minimal ; à égalité, le plus proche du niveau actuel, puis le plus bas.

**Hystérésis** : si le palier choisi diffère du niveau actuel, que la situation n'est **pas hors enveloppe** (`export > export_max` ou `import > import_max`) et que le gain de score est inférieur à `pri_score_margin`, le niveau est conservé. Hors enveloppe, le palier calculé est appliqué immédiatement.

Action rapportée : `REDUCTION`, `LIBERATION` ou `MAINTIEN`.

### 4.5 Sauts de palier

Le moteur peut passer **directement** de 100 % à 30 % (ou l'inverse) : il ne progresse pas d'un palier par trame. L'ancien moteur à un palier par trame (`domain/engine/pri.py`) n'est plus appelé (A-12).

## 5. Actionneur RRCR

### 5.1 File d'une seule consigne (`_queue_pri_target`, l. 4104)

Seule la **dernière** consigne est mémorisée ; il n'existe aucune file de vieilles trames. Si la cible vaut le niveau actuel mais qu'une ancienne cible différente est en attente, le « maintien » la remplace.

### 5.2 Boucle (`_pri_actuator_loop`, l. 4133)

Tant qu'une consigne est en attente :

1. lire le niveau courant ; s'il vaut déjà la cible, statut `OK` ;
2. appliquer le niveau (`_apply_rrcr_level`), borné à **4 s** au total ;
3. si une consigne plus récente est arrivée pendant l'envoi : statut `SUPERSEDED`, passer à la suivante ;
4. attendre le code attendu jusqu'à **5 s** (lecture toutes les 0,25 s) ; échec → `ack_rrcr = FAILED`, **pas de retour arrière** (la trame suivante décide de nouveau) ;
5. succès → `current_level = cible` et ouverture d'un ACK « N+1 » (rrcr, onduleur, réseau en `PENDING`) rattaché à la trame demandeuse.

### 5.3 Écriture des relais (`_apply_rrcr_level`, l. 4069)

Sous `_inverter_action_lock`, les relais sont commandés **un par un**, dans l'ordre L4, L3, L2, L1 (`switch.turn_on/off`, `blocking=False`, 2 s par appel). L'écriture n'est pas atomique : le code passe brièvement par des valeurs intermédiaires (A-10).

### 5.4 Libération sûre à 100 % (`async_release_pri_100`, l. 4198)

Écrit `0000` et attend la confirmation (5 s). Appelée : à l'activation de la régulation, à la désactivation de la régulation, quand `pri_enabled` passe à faux, à la fin de journée solaire, par le bouton « Libérer l'onduleur à 100 % », à l'application d'un profil, et par le délestage (option). Sans relais configurés, elle se contente de **marquer** 100 %.

## 6. ACK « N+1 » (`_validate_pending_pri_on_frame`, l. 4254)

À la première trame dont le numéro de série dépasse celui de la commande (et si le snapshot est valide) :

| ACK | Test |
|---|---|
| `ack_rrcr` | le niveau lu = le niveau commandé, sinon `FAILED` |
| `ack_inverter` | comparateur PV/plafond (§ 6.1) : `OK` sauf état `PRI_INCONSISTENT` |
| `ack_grid` | `OK` si réinjection ≤ `pri_export_acceptable_w` (150 W) et import ≤ `pri_import_acceptable_w` (200 W) ; sinon `NOK_REINJECTION` / `NOK_PRELEVEMENT` ; `NOK_DONNEES` si snapshot invalide |
| `ack_logo` | retour réel des relais (entités `pri_ret_l1` à `pri_ret_l4`, ex. LOGO NQ9..NQ12) comparé au code commandé : `OK`, `FAILED`, `ABSENT` (illisible), `NON_CONFIGURE` (aucun retour). Logique : `domain/engine/pri_feedback.py`. Informatif, ne bloque pas la commande |

### 6.1 Comparateur PV / plafond (`_update_pri_pv_comparator`, l. 4233)

```text
plafond   = (pri_step_w × 10) × niveau ÷ 100        ← 400 W × 10 = 4 000 W par défaut
erreur    = pv − plafond
niveau 0           → PV_UNKNOWN
|erreur| ≤ tol     → PV_LIMITED          (production bridée : le potentiel solaire est inconnu)
pv < plafond − tol → PV_BELOW_LIMIT      (potentiel ≥ pv mesuré)
sinon              → PRI_INCONSISTENT    (PV au-dessus du plafond : le bridage n'est pas effectif)
```

Le plafond de ce comparateur est calculé avec **`pri_step_w × 10`** et non avec `inverter_power_w` : si la puissance nominale de l'onduleur est modifiée sans modifier `pri_step_w`, les deux calculs divergent (A-04).

## 7. Fin de journée solaire (`_check_end_solar`, l. 3959)

Libère l'onduleur à 100 % quand la production est durablement faible, pour repartir de 100 % le lendemain.

1. Ignoré si la régulation est inactive ou si le mode est **Manuel** (Éco et Confort sont traités ; corrigé A-01).
2. Ignoré si le niveau est entre 0 et 99 % ou si l'état solaire est `PV_LIMITED`, `PRI_ACK_PENDING` ou `PV_UNKNOWN` : une production bridée ne mesure pas le potentiel, **aucune conclusion « fin solaire »**.
3. Si `pv < pri_end_solar_w` (5 W) : démarrer un chrono ; au bout de `pri_end_solar_confirm_s` (180 s), annuler la tâche PRI et libérer à 100 %. Sinon remettre le chrono à zéro.

Conséquence directe de l'étape 2 : tant que le niveau est inférieur à 100 %, la fin de journée n'est **jamais** détectée par ce chemin. Le niveau n'est alors libéré que par le moteur lui-même. La nuit (PV = 0), la simulation ne propose aucun palier supérieur (leur réinjection prévue serait fortement pénalisée) : le niveau reste donc **inchangé jusqu'au lever du soleil**. Au lever, le plafond bas fait apparaître « PV au plafond » et un import hors enveloppe ; le moteur simule alors les paliers supérieurs et remonte directement au bon niveau, trame après trame.

## 8. Commande manuelle (`async_set_pri_manual_level`, l. 2527)

Acceptée **uniquement en mode Manuel**, pour un niveau présent dans la table RRCR. Applique les relais, attend la confirmation (5 s) et met à jour l'état (`ack_rrcr = OK` / `FAILED`).

## 9. Interactions avec le reste

- **Boiler** : la cible 65 °C n'est autorisée que sur surplus ; le PRI traite l'excédent « résiduel » après le boiler (les deux cœurs lisent le même snapshot). Le délai de stabilisation `pri_boiler_settle_s` (30 s) existe mais `_pri_settle_ok` n'est jamais appelé (A-03).
- **Délestage** : option « libérer l'onduleur à 100 % pendant le délestage ».
- **Bus** : l'Onduleur Core publie `PRI_<résultat>` vers l'EMS à chaque trame ; il acquitte comme « traité » ou `NOK_BUSY` les messages reçus.

## 10. Paramètres de cette page

| Réglage | Défaut | Effet réel |
|---|---|---|
| `inverter_power_w` | 4 000 W | plafond de simulation |
| `pri_pv_compare_tolerance_w` | 200 W | tolérance du plafond |
| `pri_ceiling_ratio` | 0,92 | ratio « PV au plafond » |
| `network_billed_import_target_w` / `…_import_max_w` / `…_export_max_w` | 100 / 250 / 50 W | enveloppe du score |
| `pri_weight_import` / `pri_weight_export` / `pri_score_margin` | 1 / 2 / 25 | score et hystérésis |
| `pri_export_acceptable_w` / `pri_import_acceptable_w` | 150 / 200 W | ACK réseau |
| `pri_step_w` | 400 W | **uniquement** le comparateur PV (× 10) |
| `pri_end_solar_w` / `pri_end_solar_confirm_s` | 5 W / 180 s | fin de journée solaire |
| **Sans effet** | — | `pri_step_percent`, `pri_inverter_ack_tolerance_w`, `pri_up_ack_delta_w`, `pri_grid_ack_delta_w`, `pri_export_threshold_dynamic_w`, `pri_import_threshold_dynamic_w`, `pri_pv_minimum_w`, `pri_probe_margin_w`, `pri_export_optimal_w`, `pri_import_optimal_w`, `pri_boiler_settle_s` (A-03) |

## 11. Couverture par les tests

Aucun test ne couvre `InverterCore.decide`, `_pri_actuator_loop` ni les ACK (`runtime/` exige Home Assistant ; `inverter_core.py` est pourtant pur et testable sans Home Assistant : voir la proposition dans ANOMALIES.md).
