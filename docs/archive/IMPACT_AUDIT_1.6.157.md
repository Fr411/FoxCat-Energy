# FoxCat Energy 1.6.157 — Audit d'impact

## Périmètre

Version source : **1.6.156 Professional**  
Version cible : **1.6.157 — Arbitrage dynamique Day-Ahead**

Le périmètre fonctionnel nouveau est limité au **régime tarifaire Dynamique**. Les paramètres physiques du Boiler sont exposés en permanence comme télémétrie, mais ne modifient une décision que lorsque **Mode EMS = Dynamique** ET **Régime tarifaire = Dynamique**.

## Fichiers modifiés

- `README.md`
- `custom_components/foxcat_energy/config_flow.py`
- `custom_components/foxcat_energy/const.py`
- `custom_components/foxcat_energy/coordinator.py`
- `custom_components/foxcat_energy/economic_optimizer.py`
- `custom_components/foxcat_energy/engine/pri.py`
- `custom_components/foxcat_energy/inverter_core.py`
- `custom_components/foxcat_energy/manifest.json`
- `custom_components/foxcat_energy/registry.py`
- `custom_components/foxcat_energy/sensor.py`
- `custom_components/foxcat_energy/strings.json`
- `custom_components/foxcat_energy/switch.py`
- `custom_components/foxcat_energy/translations/fr.json`

## Inventaire anti-régression des fonctions

Inventaire AST direct de tous les fichiers Python du composant :

- 1.6.156 : **342 fonctions/méthodes**
- 1.6.157 : **348 fonctions/méthodes**
- Ajoutées : **6**
- Supprimées : **0**

Fonctions ajoutées :

1. `FoxCatEnergyCoordinator._boiler_thermal_view`
2. `FoxCatEnergyCoordinator._apply_dynamic_boiler_arbitrage`
3. `economic_optimizer._dynamic_day_ahead_points`
4. `economic_optimizer._best_consecutive_dynamic_window`
5. `economic_optimizer._legacy_dynamic_decision`
6. `economic_optimizer._evaluate_dynamic_market`

Aucune fonction historique n'a été renommée ou supprimée.

## Fichiers sanctuarisés, identiques bit pour bit

Les fichiers suivants ont le même SHA-256 entre 1.6.156 et 1.6.157 :

- `accounting/manager.py`
- `machine_cycle.py`
- `energy_bus.py`
- `engine/modes/eco.py`
- `engine/modes/ecs_solar.py`
- `engine/modes/manual.py`
- `engine/modes/zero_injection.py`
- `engine/modes/dynamic.py`
- `engine/tariff.py`
- `machines.py`
- `machine_learning.py`

Conséquences :

- **Accounting** : aucune modification.
- **MachineCycleManager** : aucune modification.
- **Energy Bus** : aucune modification.
- Logiques historiques Eco / ECS solaire / Manuel / Zéro injection : aucune modification.
- Le moteur dynamique historique reste intact et sert de base de repli.

## Garantie HP/HC

### economic_optimizer.py

Le nouveau moteur Day-Ahead est appelé uniquement lorsque :

`regime == TARIFF_DYNAMIC`

Le bloc HP/HC reste dans la branche historique après cette garde. La règle Compensation HP/HC est également maintenue avant la branche dynamique.

Validation automatisée : **300 scénarios HP/HC pseudo-aléatoires** ont été comparés entre 1.6.156 et 1.6.157. Tous les champs qui existaient dans `EconomicDecision` 1.6.156 sont identiques.

### inverter_core.py

La nouvelle règle de prix d'export signé est protégée par :

`tariff_regime == TARIFF_DYNAMIC`

Validation automatisée : **500 scénarios non dynamiques pseudo-aléatoires** ont comparé l'intégralité de `InverterDecision` entre 1.6.156 et 1.6.157. Résultat : **500/500 identiques**.

La politique **Compensation** reste évaluée avant toute règle dynamique et impose toujours directement **100 %**.

### coordinator.py

- Les kill-switches ne réinitialisent/reconcilient le CORE que si **mode = Dynamique** et **tarif = Dynamique**.
- L'IA solaire n'est neutralisée que sous la même double condition.
- `_apply_dynamic_boiler_arbitrage()` retourne immédiatement l'intention historique si le mode ou le tarif n'est pas Dynamique.
- Les horizons de prix forcés à 24 h ne le sont que pour `TARIFF_DYNAMIC`; tous les autres régimes conservent `economic_horizon_hours`.

## Modèle thermique Boiler

Nouveaux paramètres de configuration :

- `boiler_volume` — litres, défaut 250 L
- `boiler_element_power` — watts, défaut 1800 W
- `boiler_cold_water_temp` — °C, défaut 15 °C

Formule :

`E_th [kWh] = Volume[L] × 1.163 × max(T_consigne - T_mesurée, 0) / 1000`

La consigne utilisée pour l'énergie manquante est la température de confort Boiler `boiler_temp_normal_c`.

Durée estimée :

`durée[h] = E_th[kWh] / (P_résistance[W] / 1000)`

Ces calculs sont exposés comme télémétrie même hors Dynamique, mais ne changent aucune décision HP/HC.

## Arbitrage dynamique

Indice relatif :

`Position = (Prix_actuel - Prix_min) / (Prix_max - Prix_min)`

Bornes :

- `Position < 0.35` : **BAS** — charge/stockage possible.
- `0.35 <= Position <= 0.70` : **MEDIAN** — surplus local strict.
- `Position > 0.70` : **HAUT** — nouveau prélèvement opportuniste interdit.

Le prix actuel est réinjecté dans le slot horaire courant avant calcul, afin qu'une série Day-Ahead légèrement retardée ne remplace pas le prix réellement actif.

Une réservation thermique ne peut provoquer une charge réseau que dans la plage **BAS**. En **MEDIAN**, le surplus local doit couvrir la résistance. En **HAUT**, aucune nouvelle charge réseau Boiler n'est autorisée hors confort ECS minimal.

Si moins de 6 points Day-Ahead sont exploitables, FoxCat utilise le comportement dynamique standard 1.6.156.

## Compatibilité du réglage historique « prix négatif »

`dynamic_negative_price_charge_enabled` est conservé.

- activé : le comportement historique de charge réseau à prix négatif, y compris le stockage 65 °C, reste disponible ;
- désactivé : un prix négatif ne peut pas être réintroduit indirectement comme charge réseau par la nouvelle réservation Day-Ahead ; seul le confort ECS minimum ou un surplus local suffisant peut autoriser la chauffe.

`engine/modes/dynamic.py` est identique bit pour bit à 1.6.156.

## Prix d'export dynamique signé / PRI

Sous **Dynamique** uniquement :

- valeur export `> 0` : PRI libéré directement à **100 %** ;
- valeur export `< 0` : comportement prédictif de quasi-zéro injection ;
- valeur nulle/indisponible : repli sur le comportement prédictif historique ;
- Compensation : **100 %** avant toute autre règle.

Le signe utilisé est la **valeur économique normalisée** déjà produite par FoxCat : positif = recette, négatif = coût pour exporter.

## Kill-switches

Nouveaux switches :

- `switch.foxcat_predictive_pricing_enabled`
- `switch.foxcat_solar_forecast_arbitrage`

Effet :

- prédictif prix OFF : repli sur le comportement dynamique standard ;
- arbitrage solaire OFF : la prévision solaire n'influence plus l'évaluation du mode Dynamique, mais la télémétrie IA continue d'exister ;
- HP/HC : aucun effet décisionnel.

## Sécurités sanctuarisées

- Le contrôle de température de sécurité Boiler reste exécuté **avant** toute stratégie dynamique.
- Le seuil `boiler_temp_safety_c`, 68 °C par défaut, n'est pas modifié.
- Les commandes utilisateur restent prioritaires dans la hiérarchie existante, sauf sécurité thermique.
- `MachineCycleManager` est inchangé.
- Un cycle protégé déjà actif est toujours retourné comme `CYCLE_EN_COURS` avec `allow_start=True` par le comparateur économique.
- Le confort ECS minimum bloque les nouveaux démarrages économiques secondaires pendant le besoin prioritaire.

## Tests exécutés hors Home Assistant

Le runtime de cette session ne contient pas Home Assistant ; les tests d'intégration HA réels doivent donc être exécutés sur une instance de staging. Les validations Python pures exécutées sont :

- compilation de tous les `.py` : OK ;
- parsing JSON : OK ;
- 300 scénarios économiques HP/HC : parité 1.6.156 = 1.6.157 ;
- 500 scénarios InverterCore non dynamiques : parité complète ;
- bandes dynamiques BAS / MEDIAN / HAUT : OK ;
- interdiction de charge réservée en MEDIAN / HAUT : OK ;
- kill-switch prédictif -> repli standard : OK ;
- cycle machine protégé : OK ;
- export dynamique positif -> PRI 100 % : OK ;
- export dynamique négatif -> bridage prédictif : OK ;
- Compensation -> PRI 100 % : OK ;
- `engine/pri.py` : règle signée dynamique OK ;
- `engine/modes/dynamic.py` : identité binaire avec 1.6.156.

## Conclusion d'impact

L'implémentation ajoute une couche de décision **strictement dynamique** autour des moteurs validés. Les blocs critiques historiques ne sont pas remplacés : ils sont soit inchangés, soit appelés comme repli. La validation automatique confirme la parité HP/HC sur les scénarios testés ; la validation finale doit être complétée par le plan d'essai Home Assistant fourni avec la release.
