# Audit anti-régression — FoxCat Energy 1.6.153

## Comparaison

- Référence : FoxCat Energy 1.6.152
- Cible : FoxCat Energy 1.6.153
- Fonctions/méthodes 1.6.152 : **309**
- Fonctions/méthodes 1.6.153 : **331**
- Fonctions/méthodes supprimées : **0**
- Fonctions/méthodes ajoutées : **22**

## Fonctions ajoutées

### `economic_optimizer.py`
- `EconomicDecision.as_dict`
- `_float`
- `_parse_datetime`
- `_price_at`
- `average_price`
- `best_start_window`
- `build_hphc_points`
- `evaluate_market`
- `extract_price_points`
- `extract_price_points.add`
- `extract_price_points.walk`
- `merge_price_points`
- `recommend_flexible_load`

### `coordinator.py`
- `_economic_series_from_entity`
- `_economic_import_points`
- `_economic_export_points`
- `_economic_view`
- `_on_economic_price_event`

### `config_flow.py`
- `_dynamic_export_sign_selector`

### `sensor.py`
- `FoxCatEconomicDecisionSensor.__init__`
- `FoxCatEconomicDecisionSensor.native_value`
- `FoxCatEconomicDecisionSensor.extra_state_attributes`

## Fonctions historiques supprimées

**Aucune.**

## Fonctions modifiées volontairement

- `InverterCore.decide` : uniquement la branche **Compensation**, qui cible maintenant directement 100 % conformément à la règle validée. La branche prédictive **Injection facturée** reste inchangée.
- `FoxCatEnergyCoordinator._tariff_start_favorable` : utilise le nouveau comparateur économique pour les nouveaux démarrages automatiques de machines. Le comportement historique reste disponible si l'optimiseur économique est désactivé.
- `FoxCatEnergyCoordinator.async_reconcile_machines` : transmet la recommandation économique calculée une seule fois par réconciliation. Les cycles protégés conservent leur priorité absolue.
- `FoxCatEnergyCoordinator.prices` : normalisation explicite de la convention du signe du prix d'export dynamique.

## Éléments explicitement conservés

- Deux cœurs indépendants et cadencés par le capteur réseau.
- Machine à états EMS.
- Energy Bus et ACK/NOK inter-cœurs.
- Worker RRCR et logique de trames fraîches.
- Algorithme prédictif PRI de la politique Injection facturée.
- Machine à états des cycles machines.
- Commandes utilisateur machines et Boiler.
- Collecte passive des profils machines.
- Accounting énergétique natif.
- Fallback et Watchdog.

## Energy Bus

Le comparateur économique ne publie **aucun message** sur Energy Bus. Les recommandations tarifaires restent hors bus.
