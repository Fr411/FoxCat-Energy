# Audit anti-régression — FoxCat Energy 1.6.151 → 1.6.152

## Résumé

- Fonctions / méthodes 1.6.151 : **293**
- Fonctions / méthodes 1.6.152 : **309**
- Fonctions supprimées : **0**
- Fonctions ajoutées : **16**

## Fonctions ajoutées

### Coordinator

- `FoxCatEnergyCoordinator._machine_bus_context`
- `FoxCatEnergyCoordinator._on_machine_telemetry_event`
- `FoxCatEnergyCoordinator._record_machine_learning`
- `FoxCatEnergyCoordinator._schedule_learning_save`

### Collecteur passif machines

- `MachineLearningRecorder.__init__`
- `MachineLearningRecorder._append_point`
- `MachineLearningRecorder._compact_points`
- `MachineLearningRecorder._finish_cycle`
- `MachineLearningRecorder._integrate`
- `MachineLearningRecorder._new_cycle`
- `MachineLearningRecorder._num`
- `MachineLearningRecorder._save_due`
- `MachineLearningRecorder.dump`
- `MachineLearningRecorder.observe`
- `MachineLearningRecorder.restore`
- `MachineLearningRecorder.view`

## Fonctions supprimées

Aucune.

## Gel des moteurs vérifié

Comparaison binaire 1.6.151 → 1.6.152 :

- `inverter_core.py` : **inchangé**
- `engine/pri.py` : **inchangé**
- tout `engine/*.py` et `engine/modes/*.py` : **inchangé**
- `machine_cycle.py` : **inchangé**
- `accounting/manager.py` : **inchangé**

La machine à états actuelle, le PRI prédictif et les stratégies EMS ne sont donc pas modifiés par cette release.

## Modifications additives contrôlées

- `machine_learning.py` : nouveau collecteur passif.
- `machines.py` : ajout des références optionnelles courant/tension.
- `config_flow.py` : sélection optionnelle des capteurs courant/tension.
- `coordinator.py` : observation passive + enrichissement de la trame Energy Bus + valeurs tarifaires génériques.
- `energy_bus.py` : correction de collision `origin` uniquement.
- `sensor.py` : capteurs d’observation et de tarification.
- `registry.py` : rôles natifs supplémentaires pour le dashboard.
- `dashboard/dashboard.yaml` : migration des KPI vers les compteurs natifs FoxCat.

## Tests statiques

- Compilation Python complète : **OK**.
- JSON : **OK**.
- YAML dashboard : **OK**.
- Rôles dashboard : **168 utilisés / 168 résolus**, aucun rôle orphelin.
- Test synthétique du collecteur machine : **OK** (cycle archivé, énergie intégrée, dump/restore).
- Test `EnergyBus.publish_ems_intent()` avec `origin` explicite : **OK**, absence de collision de keyword.

## Conclusion

La 1.6.152 est additive par rapport à la 1.6.151. Aucune fonction Python historique de la 1.6.151 n’a été supprimée et les moteurs décisionnels gelés sont inchangés.
