# FoxCat Energy 1.6.159 — Audit d'impact

## Règle d'isolement

Le nouveau Dynamic Scheduler est autorisé uniquement si :

- `mode == Prix dynamique` ;
- `tariff_regime == Dynamique` ;
- l'optimiseur économique est actif ;
- le prédictif prix est actif.

Hors de ce périmètre, le planner est exposé comme inactif et ne donne aucune autorisation de départ.

## Fichiers moteur modifiés

- `accounting/manager.py`
- `binary_sensor.py`
- `const.py`
- `coordinator.py`
- `dynamic_scheduler.py` (nouveau)
- `economic_optimizer.py`
- `number.py`
- `registry.py`
- `sensor.py`
- `manifest.json`
- `dashboard/dashboard.yaml`

## Fichiers sanctuarisés vérifiés identiques bit pour bit

- `machine_cycle.py`
- `energy_bus.py`
- `machines.py`
- `machine_learning.py`
- `engine/load_guard.py`
- `engine/modes/eco.py`
- `engine/modes/ecs_solar.py`
- `engine/modes/manual.py`
- `engine/modes/zero_injection.py`

## Accounting

Aucun netting physique : import et export sont intégrés dans des registres monotones séparés. Les revenus/coûts de réinjection n'interviennent qu'en euros.

Lors d'un changement de régime en cours de journée, les anciens kWh restent dans le bucket où ils ont été acquis. Le total physique journalier continue indépendamment.

## Machines

Le scheduler ne remplace pas MachineCycleManager. Il ne décide que d'un **nouveau départ automatique**. Les protections de cycle restent souveraines.

## Boiler

Les boosts ajoutés sont derrière le double verrou Mode Dynamique + régime Dynamique. Les sécurités thermiques et overrides utilisateur sont traités avant l'arbitrage Day-Ahead.
