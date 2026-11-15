# Rapport d'anomalies — audit des algorithmes (V1.7.6)

Audit **sans correction** : chaque point est décrit, localisé et accompagné d'un scénario ou d'une preuve, et d'une proposition. La gravité est celle de l'effet observable par l'utilisateur.

| Gravité | Sens |
|---|---|
| **Critique** | une fonction principale tombe en panne dans un cas courant |
| **Haute** | résultat faux ou comportement contraire à l'intention, dans un cas courant |
| **Moyenne** | écart réel, mais limité à une configuration ou à un réglage |
| **Basse** | dette technique, texte trompeur, cas rare |

**Statut** : **A-22, A-16, A-01, A-14, A-03 et A-29 sont corrigées** (un commit et des tests chacune) ; les autres points restent ouverts.

**Preuves** : les points marqués ✔ ont été **reproduits par un petit calcul** (cité). Les autres sont établis **par lecture du code** (fichier et fonction cités) ; je n'ai rien essayé dans Home Assistant.

## Résumé

| ID | Gravité | Titre |
|---|---|---|
| ~~A-22~~ | **Critique** | Tarif dynamique : le planificateur plante dès qu'un cycle machine est protégé ✔ |
| ~~A-16~~ | Haute | Prix au quart d'heure : un seul quart d'heure par heure est retenu ✔ |
| ~~A-01~~ | Haute | Mode Confort : PRI inactif et onduleur jamais libéré |
| A-02 | Moyenne | Code et réglages liés aux anciens modes devenus inatteignables |
| ~~A-03~~ | Moyenne | 22 entités et 2 réglages de formulaire sans aucun effet (signalés inactifs) |
| A-04 | Moyenne | Deux « puissances d'onduleur » incohérentes (`pri_step_w` vs `inverter_power_w`) |
| A-07 | Moyenne | Vérification du boiler : `float(None)` si l'attribut `temperature` est vide |
| ~~A-14~~ | Moyenne | Prix HP/HC affichés et prix « suivant » décalés des compléments de période ✔ |
| A-15 | Moyenne | « Contrat saisi » ignore « tout compris » et les composantes réseau/taxes |
| A-17 | Moyenne | Seuils Day-Ahead réglables ignorés par la décision économique |
| A-23 | Moyenne | Gestion machine désactivée = prise coupée à chaque réconciliation (à confirmer) |
| A-26 | Moyenne | V2H non arrêté quand on coupe la régulation |
| A-05 | Basse | Détection « Compensation » par sous-chaîne dans un texte |
| A-06 | Basse | ACK boiler « NOK » sans correction |
| A-08 | Basse | Vitesses de chauffe/refroidissement du boiler codées en dur |
| A-09 | Basse | Trois politiques réseau utilisent le même algorithme PRI ✔ |
| A-10 | Basse | Relais RRCR écrits un par un (codes intermédiaires) |
| A-11 | Basse | Logique heures creuses appliquée même en contrat mono-horaire |
| A-12 | Basse | Ancien moteur PRI (`pri.py`) importé mais jamais appelé |
| A-13 | Basse | Override boiler sans expiration ni persistance |
| A-18 | Basse | Blocs creux/pic du planificateur supposent des points horaires |
| A-19 | Basse | `async_release_pri_100` n'annule pas une consigne PRI en attente |
| A-20 | Basse | Vue économique recalculée plusieurs fois par trame |
| A-21 | Basse | Comptabilité : copies profondes à chaque trame |
| A-24 | Basse | Le délestage compte aussi les passages de la minuterie de 30 s |
| A-25 | Basse | Chauffage : le surplus n'est pas réparti entre systèmes |
| A-27 | Basse | Prompt IA : plages HP/HC écrites en dur |
| ~~A-29~~ | Moyenne | Capacitaire flamand : seule la pointe du mois en cours comptait (corrigée) |
| A-28 | Basse | Arbitrage d'export virtuel : comparaison à des libellés inexistants |

---

## A-22 · Critique · Tarif dynamique : le planificateur plante avec un cycle protégé ✔ — CORRIGÉE

**Où** : `domain/loads/flexible_load_planner.py`, `build_flexible_load_plan` (ligne « cycle protégé » : `datetime.fromisoformat(cycles[...]['expected_end_at'])`).

**Cause** : `MachineCycleManager.snapshot()` renvoie `expected_end_at` sous forme de `datetime`, alors que le planificateur la lit avec `datetime.fromisoformat`, qui n'accepte qu'une chaîne.

**Preuve** (exécutée) : avec un cycle démarré par `force_start`, `cycles["washer"]["expected_end_at"]` est un `datetime`, puis `build_flexible_load_plan(...)` lève `TypeError: fromisoformat: argument must be str`.

**Conséquences** (contrat dynamique, mode ≠ Manuel, dès qu'une machine pilotée est en cycle protégé : bouton « Démarrer », puissance détectée, cycle externe) :

- `_economic_view` lève → `_build_data` lève → plus de rafraîchissement des entités ;
- `machine_states()` (appelé par la comptabilité à chaque trame EMS) lève → la **trame EMS finit en `ERROR`** (`_run_dispatched_core`) : plus de décision boiler ni de comptabilité pendant le cycle ;
- `async_user_start_machine` plante juste après avoir allumé la prise.

**Correction appliquée** : `_as_datetime` accepte un `datetime`, une chaîne ISO ou une valeur absente/invalide (durée par défaut). Tests : `ProtectedCyclePlannerTests` (avec le vrai `MachineCycleManager.snapshot()`). *Reste proposé* : protéger `_economic_view` par un `try/except`.

**Proposition d'origine** : accepter `datetime` **ou** chaîne (`value if isinstance(value, datetime) else datetime.fromisoformat(value)`), et ajouter un test qui passe le résultat réel de `MachineCycleManager.snapshot()` ; protéger `_economic_view` par un `try/except` qui journalise et renvoie une vue vide plutôt que de casser la trame.

## A-16 · Haute · Prix au quart d'heure : un seul quart d'heure par heure retenu ✔ — CORRIGÉE

**Où** : `domain/pricing/economic_optimizer.py`, `_dynamic_day_ahead_points`.

**Cause** : les points sont ramenés à une clé « début de l'heure » dans un dictionnaire ; chaque point d'une même heure **écrase** le précédent.

**Preuve** (exécutée) : quatre quarts d'heure 0,10 / 0,12 / 0,30 / 0,50 €/kWh donnent **un seul point à 0,50 €/kWh**.

**Conséquences** : avec des prix au quart d'heure (cas des contrats dynamiques belges), la position sur la courbe, la bande BAS/MEDIAN/HAUT, le créneau de réservation du boiler (blocs de **plein heures**), `best_future_buy` et l'économie potentielle reposent sur le **dernier** quart d'heure de chaque heure, qui n'est pas représentatif. Les blocs « creux / pic » du planificateur supposent aussi des points horaires (A-18).

**Correction appliquée** : chaque heure est la **moyenne** de ses points (`_dynamic_day_ahead_points`). Tests : `QuarterHourDayAheadTests` (moyenne horaire, doublons, fenêtre consécutive, courbe de marché). *Reste ouvert* : `_group_price_zones` suppose encore des points horaires (A-18).

**Proposition d'origine** : conserver tous les points, ou agréger explicitement (moyenne pondérée par la durée) ; adapter `_best_consecutive_dynamic_window` et `_group_price_zones` à la granularité réelle ; ajouter des tests sur une courbe de 96 points par jour.

## A-01 · Haute · Mode Confort : PRI inactif et onduleur jamais libéré — CORRIGÉE

**Où** : `runtime/coordinator.py` `_pri_guard` (mode ∈ {Éco, « Zéro injection », « Dynamique »}), `_check_end_solar` (mode ∈ {Éco, « Zéro injection »}), `async_set_mode`.

**Cause** : le mode ne vaut plus que Éco, Confort ou Manuel (A-02). Seul **Éco** passe ces gardes.

**Conséquences** :

1. En **Confort**, le PRI ne tourne jamais : avec une politique « Zéro injection » ou « Injection non valorisée », **la réinjection n'est pas limitée**.
2. En passant d'Éco (PRI à par exemple 30 %) à Confort, **rien ne libère l'onduleur** : la garde échoue (niveau conservé) et la fin de journée solaire est ignorée ; l'onduleur reste bridé jusqu'au retour en Éco ou à la désactivation de « Réduction de puissance onduleur » (qui, elle, libère).

**Correction appliquée** : le PRI et la fin de journée solaire fonctionnent dans tous les modes sauf Manuel (`pri_mode_allowed`) ; passer en Manuel libère l'onduleur à 100 % si le PRI est activé. Tests : `PriModeTests`. *Décision à confirmer* : Confort pilote désormais le PRI comme Éco.

**Proposition d'origine** : décider si Confort doit piloter le PRI ; dans tous les cas, libérer l'onduleur à 100 % lors d'un changement de mode qui désactive la garde, et remplacer les listes de modes par `mode != Manuel`.

## A-02 · Moyenne · Code et réglages liés aux anciens modes devenus inatteignables

**Où** : comparaisons avec `MODE_DYNAMIC` (« Dynamique »), `MODE_ZERO` (« Zéro injection »), `MODE_ECS` (« Bihoraire »), alors que `settings["mode"]` est toujours Éco/Confort/Manuel (`async_set_mode`, migration).

**Inatteignable** : `_on_economic_price_event` (réconciliation des machines au changement de prix), `async_handle_price_change` (réévaluation immédiate du boiler au changement de prix, notamment le passage sous 0 €/kWh), `_dynamic_tariff_ok` (toujours vrai), `_apply_dynamic_boiler_arbitrage` (jamais appelée), `evaluate_ecs_solar`, `evaluate_zero_injection`, la branche dynamique d'`evaluate_mode`, `domain/engine/modes/dynamic.py`, les noms d'action `ECS_MODULE_ON_45` / `BOILER_ON_45_PRICE`, et `domain/engine/flexible_boiler.py` (qui importe en plus une constante absente de `const.py` : `DISTRIBUTION_WALLONIA_IMPACT`, donc une erreur d'import s'il était un jour importé).

**Conséquence visible** : un changement de prix n'est pas pris en compte immédiatement ; il attend la trame réseau suivante.

**Proposition** : soit réactiver ces chemins avec la condition « tarif dynamique », soit les retirer (déplacer dans `trash/`), et garder un seul concept (régime tarifaire) pour décider.

## A-03 · Moyenne · 22 entités et 2 réglages sans aucun effet — CORRIGÉE (signalés inactifs)

Des entités `number` / `switch` existent mais leur clé n'est lue nulle part (14 entités) ou seulement par du code inatteignable (8 entités) ; deux réglages de formulaire (`pri_step_percent`, `dynamic_preferred_network_max_eur_kwh`) sont lus mais sans effet :

| Domaine | Clés |
|---|---|
| Boiler (ECS solaire) | `agressivite_ecs`, `coverage_solar_min_percent`, `surplus_pv_min_agressivite_w`, `import_boiler_max_w` |
| Dynamique | `dynamic_negative_price_charge_enabled`, `dynamic_grid_charge_threshold_eur_kwh`, `dynamic_preferred_network_max_eur_kwh` |
| PRI | `pri_step_percent`, `pri_inverter_ack_tolerance_w`, `pri_up_ack_delta_w`, `pri_grid_ack_delta_w`, `pri_export_threshold_dynamic_w`, `pri_import_threshold_dynamic_w`, `pri_pv_minimum_w`, `pri_probe_margin_w`, `pri_export_optimal_w`, `pri_import_optimal_w` |
| Protection | `high_load_confirm_s`, `high_load_restore_s` |
| Dynamique (suite) | `dynamic_injection_lucrative_threshold` |
| Autres | `autoconsommation_cible_percent`, `autoconsommation_min_percent`, `solar_window_min_minutes`, `pri_boiler_settle_s` (la méthode `_pri_settle_ok` n'est jamais appelée) |

Le texte du README « avec un prix négatif, le boiler peut charger sur le réseau » est donc **inexact** (le boiler dynamique ne chauffe sur le réseau que jusqu'à 45 °C et n'a pas de règle « prix négatif »).

**Correction appliquée** : les 22 entités sont dans `INACTIVE_SETTINGS` (`const.py`) : créées **désactivées**, en catégorie diagnostic, avec l'attribut `statut: inactif` ; elles sont conservées pour ne pas casser les tableaux de bord et les profils. `pri_step_percent` (variable inutilisée) a été retiré du moteur. Test `test_inactive_settings.py` : un réglage lu par aucun code actif doit être déclaré inactif. README et manuel corrigés. *Reste ouvert* : `dynamic_preferred_network_max_eur_kwh` (champ de formulaire) et la décision de retirer ou d'implémenter ces réglages.

**Proposition d'origine** : masquer ces entités ou les retirer ; corriger le README.

## A-04 · Moyenne · Deux « puissances d'onduleur » incohérentes

**Où** : `_update_pri_pv_comparator` calcule le plafond avec `pri_step_w × 10` (400 W × 10 = 4 000 W), alors que le moteur utilise `inverter_power_w` (4 000 W par défaut).

**Conséquence** : si l'utilisateur renseigne `inverter_power_w = 8 000` sans toucher `pri_step_w`, le comparateur voit un plafond de 4 000 W : états `PV_LIMITED` / `PRI_INCONSISTENT` faux, `ack_inverter` en échec, et détection de fin de journée perturbée (états `PV_LIMITED` ignorés).

**Proposition** : utiliser `inverter_power_w` partout.

## A-07 · Moyenne · Vérification du boiler : `float(None)`

**Où** : `_verify_boiler_execution` (`setpoint = float(climate.attributes.get("temperature", 0))`).

**Cause** : si l'attribut `temperature` existe avec la valeur `None` (fréquent sur un thermostat éteint), `float(None)` lève `TypeError`, attrapé par le `except` général : statut `FAILED` avec une raison trompeuse, **même quand la commande a réussi**.

**Proposition** : `float(value or 0)` et ne lire la consigne que pour les commandes de chauffe.

## A-14 · Moyenne · Prix HP/HC décalés des compléments de période ✔ — CORRIGÉE

**Où** : `prices()` appelle `final_client_price(hp, now, …)` et `final_client_price(hc, now, …)` : les **deux** reçoivent le complément de la **période courante**.

**Preuve** (exécutée) : avec un complément HP de 0,05 €/kWh et HC de 0, de jour (HP) le prix HC 0,25 devient **0,30** ; la nuit (HC) le prix HP 0,35 reste **0,35** (il aurait dû devenir 0,40).

**Conséquence** : le prix **actif** est correct ; `hp_price`, `hc_price`, `next_buy` et les séries HP/HC de l'optimiseur sont faux dès que les compléments HP et HC diffèrent.

**Correction appliquée** : `final_client_price(..., period="HP"|"HC")` et `hp_hc_final_prices` ; `prices()` les utilise. Tests : `tests/test_tariff_period_adders.py`.

**Proposition d'origine** : évaluer chaque prix à un instant situé dans sa propre période.

## A-15 · Moyenne · « Contrat saisi » ignore « tout compris » et les composantes

**Où** : `domain/tariff/legacy.py`, `tariff_from_settings`.

**Conséquence** : si `price_is_all_in` est coché (ou `price_curve_is_final` décoché avec des composantes réseau/taxes/contrat), le tarif « Contrat saisi » ajoute quand même les compléments HP/HC/Impact et ignore les composantes : l'écart avec le tarif **actuel** (observé) est faussé.

**Proposition** : reporter `all_in` et les composantes dans `adder_flat` / `all_in`.

## A-17 · Moyenne · Seuils Day-Ahead réglables ignorés par la décision économique

**Où** : `_evaluate_dynamic_market` n'utilise les réglages utilisateur que si `mode == "Dynamique"` (A-02) ; sinon constantes 35 % / 70 %.

**Conséquence** : la bande BAS/MEDIAN/HAUT, `charge_now`, `flexible_start` et donc les recommandations par machine ignorent `dynamic_favorable_position_pct` et `dynamic_high_position_pct`, alors que l'analyseur, le boiler dynamique et le planificateur Day-Ahead les respectent : deux échelles différentes pour un même réglage.

## A-23 · Moyenne · Gestion machine désactivée : la prise est coupée (à confirmer)

**Où** : `async_reconcile_machines` : `doit_être_ON = cycle_actif OU garder_allumée OU (gestion ET autorisée ET tarif OK ET pas de bloc)`.

**Conséquence** : pour une machine dont la gestion automatique est **désactivée**, la prise reçoit `turn_off` à chaque réconciliation tant qu'aucun cycle n'est détecté (et un cycle ne peut pas démarrer prise coupée). La désactivation de la gestion ne « rend pas la main » ; elle coupe l'alimentation. À confirmer avec l'intention du produit.

**Proposition** : si la gestion est désactivée, ne rien envoyer (ou laisser la prise allumée).

## A-26 · Moyenne · V2H non arrêté quand on coupe la régulation

**Où** : `_evaluate_v2h` n'est appelée que depuis `_evaluate_high_load`, lui-même appelé uniquement si la régulation est active. `async_set_setting("regulation_active", False)` n'arrête pas le V2H.

**Conséquence** : un V2H en décharge reste en décharge si l'utilisateur coupe la régulation.

**Proposition** : appeler l'arrêt du V2H lors de la désactivation de la régulation et du passage en Manuel.

## Gravité basse

- **A-05** : `async_command_boiler`/cœur : l'ARRÊT « énergétique » est reconnu en cherchant `achat réseau` ou `hp` dans le **texte** de la raison (`_core_process_frame`). Un changement de libellé casse la règle ; utiliser un code d'origine.
- **A-06** : un ACK `NOK` du cœur EMS est consigné mais ne provoque ni nouvelle tentative ni pénalité.
- **A-08** : `thermal_deadline` et `ecs_last_departure` supposent 10 °C/h de chauffe et 0,5 °C/h de refroidissement ; le modèle thermique (volume, puissance) n'est pas utilisé.
- **A-09** ✔ : « Injection non valorisée » et « Zéro injection » (et « Injection tarifée » avec valeur ≤ 0) exécutent le **même** algorithme PRI ; la différence passe uniquement par `export_value` (0 pour les deux premières). Vérifié par calcul : mêmes décisions sur 5 situations.
- **A-10** : `_apply_rrcr_level` écrit les 4 relais séquentiellement ; l'onduleur peut lire un code intermédiaire (un autre niveau) pendant 1 à 2 s.
- **A-11** : la logique « heures creuses » du boiler (démarrage réseau avec failback) s'applique à toutes les structures, y compris le mono-horaire, avec les plages HP par défaut (07–11 et 17–22).
- **A-12** : `domain/engine/pri.py` (`decide_zero`, `decide_dynamic`, `house_target_level`) est importé par le coordinateur mais jamais appelé.
- **A-13** : `boiler_user_override` (FORCE_ON / FORCE_OFF) n'expire jamais et n'est pas persisté ; un FORCE_OFF oublié maintient le boiler à l'arrêt.
- **A-18** : `_group_price_zones` place la fin d'un bloc à « dernier point + 1 h » ; faux pour des points de 15 min.
- **A-19** : `async_release_pri_100` n'annule pas une consigne en attente (`_pri_requested`) ; une consigne déjà demandée peut être appliquée juste après la libération.
- **A-20** : `_economic_view` est recalculée à chaque `_build_data`, à chaque `machine_states` (et pour chaque machine via `_tariff_start_favorable`) et dans le cœur EMS : plusieurs fois par trame.
- **A-21** : `EnergyAccounting.process` appelle `view()` (4 copies profondes) à chaque trame pour valider.
- **A-24** : `_evaluate_high_load` est appelée par chaque trame **et** par chaque rafraîchissement de 30 s ; les « trames hautes/basses » comptent donc aussi des passages sans nouvelle publication.
- **A-25** : le chauffage évalue chaque système avec le **même** surplus total (« surplus partagé » n'est pas réparti) ; deux PAC peuvent chacune prendre le décalage complet.
- **A-27** : le prompt de l'agent IA contient « HC : 22:00-07:00 et 11:00-17:00 » écrit en dur.
- **A-28** : `trading/virtual_assets/config.py` autorise l'arbitrage d'export si `price_source ∈ {"dynamic", "integration"}`, valeurs qui n'existent pas (les vraies sont « Dynamique Day-Ahead » et « Intégration externe ») ; seul `tariff_regime == "Dynamique"` fonctionne.

---

## A-29 · Moyenne · Capacitaire flamand : pointe du mois en cours seulement — CORRIGÉE

**Constat** (après recherche des règles officielles, Fluvius et VREG) : la facture flamande utilise la **moyenne des pointes mensuelles sur au plus 12 mois**, chacune au minimum 2,5 kW ; FoxCat n'utilisait que la pointe du **mois en cours** (`max(pointe, 2,5)`), donc une estimation instable (un seul pic du mois la faisait grimper) et différente de la facture.

**Correction** : `billed_peak_kw` (moyenne des mois connus, plancher 2,5 kW, ≤ 12 mois), historique des pointes mémorisé par `ConsumptionSeries` (13 mois, persisté, reconstitué depuis les créneaux conservés), attributs `pointe_facturee_kw` et `mois_pris_en_compte` sur « Coûts réseau • Ce mois ». Tests : `tests/test_capacity_rolling_average.py`. Détail et sources : `04_tarification.md` § 5.1.

## Tests proposés (par ordre de valeur)

1. **A-22** : passer le vrai `MachineCycleManager.snapshot()` à `build_flexible_load_plan` ; couvrir aussi `machine_states()` en tarif dynamique.
2. **A-16** : courbes de 96 quarts d'heure : position, bande, bloc consécutif, créneau de réservation.
3. **`InverterCore.decide`** (module pur, sans Home Assistant) : nuit/lever, politiques, hystérésis, sauts de palier.
4. **`evaluate_eco`** (HP, cycle minimum, boost, `solar_full`) et **`evaluate_dynamic_boiler_v2`** (8 branches).
5. **`prices()` / `final_client_price`** avec compléments HP ≠ HC (A-14) et `price_is_all_in` (A-15).
6. **`peak_shaving`** : confirmation par trames et rôle de la minuterie de 30 s (A-24).
7. Ventilation HP/HC et dynamique de la comptabilité, rollover de minuit, économies FoxCat.
