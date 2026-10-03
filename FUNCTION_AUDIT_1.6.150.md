# Audit anti-régression — FoxCat Energy 1.6.1-101 → 1.6.150

## Résultat

- Fonctions / méthodes 1.6.1-101 : **278**
- Fonctions / méthodes 1.6.150 : **286**
- Fonctions / méthodes supprimées : **0**
- Fonctions / méthodes ajoutées : **8**

## Fonctions ajoutées

- `coordinator.py::_async_ems_service_call`
- `coordinator.py::_execute_boiler_command`
- `coordinator.py::_pri_actuator_loop`
- `coordinator.py::_queue_pri_target`
- `coordinator.py::_run_dispatched_core`
- `energy_bus.py::expire_frames`
- `energy_bus.py::mark_frame_core`
- `energy_bus.py::publish_message`

## Fonctions remplacées ou modifiées sans suppression

- `_async_metronome_report` : chaque publication réelle devient une trame immédiate.
- `_async_metronome_watchdog` : ne génère plus de trames périodiques synthétiques.
- `_async_metronome_pulse` : crée un snapshot commun et lance les deux cœurs en parallèle.
- `_on_grid_event` : la voie legacy cadence désormais elle aussi les deux cœurs.
- `async_handle_inverter_grid_frame` : décision PRI séparée de l'action physique RRCR.
- `async_handle_house_frame` : utilisation du snapshot commun de la trame et communication Energy Bus.
- `async_command_boiler` : décision EMS non bloquante, exécution physique hors trame.
- `_activate_high_load_shed` : libération PRI non bloquante.
- `_apply_rrcr_level` : appels RRCR non bloquants et bornés.
- `_validate_pending_pri_on_frame` : validation N+1 rattachée au serial exact de la trame.
- `_run_pri_frame` : calcul immédiat, worker RRCR séparé.
- `InverterCore.decide` : remontée autorisée immédiatement sur import hors enveloppe.
- `EnergyBus` : messages bidirectionnels, statut de traitement par cœur et timeout de trame.

## Conclusion

Aucune fonction Python présente dans 1.6.1-101 n'a été supprimée. La 1.6.150 est une refonte du chemin d'exécution des trames et des commandes physiques, pas une réduction fonctionnelle.
