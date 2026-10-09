# Audit anti-régression — FoxCat Energy 1.6.156

Base comparée : **FoxCat Energy 1.6.155 Professional**.

- Fonctions/méthodes 1.6.155 : **337**
- Fonctions/méthodes 1.6.156 : **342**
- Ajoutées : **5**
- Supprimées : **0**

## Fonctions ajoutées

- `FoxCatEnergyCoordinator._financial_status_view` — `custom_components/foxcat_energy/coordinator.py`
- `FoxCatEnergyCoordinator._status_notification_signature` — `custom_components/foxcat_energy/coordinator.py`
- `FoxCatEnergyCoordinator.async_refresh_persistent_status_notification` — `custom_components/foxcat_energy/coordinator.py`
- `FoxCatEnergyCoordinator.async_refresh_persistent_status_notification.euro_kwh` — `custom_components/foxcat_energy/coordinator.py`
- `FoxCatEnergyCoordinator.async_set_updated_data` — `custom_components/foxcat_energy/coordinator.py`

## Fonctions supprimées

- Aucune.

## Moteurs critiques

- `custom_components/foxcat_energy/inverter_core.py` : **inchangé**
- `custom_components/foxcat_energy/engine/pri.py` : **inchangé**
- `custom_components/foxcat_energy/energy_bus.py` : **inchangé**
- `custom_components/foxcat_energy/economic_optimizer.py` : **inchangé**
- `custom_components/foxcat_energy/machine_cycle.py` : **inchangé**
- `custom_components/foxcat_energy/machine_learning.py` : **inchangé**
- `custom_components/foxcat_energy/accounting/manager.py` : **inchangé**

## Périmètre de la version

- Ajout d’une notification persistante de statut EMS, mise à jour sous un identifiant stable.
- Ajout d’un état financier lisible dérivé de la décision économique existante.
- Ajout d’un switch utilisateur permettant d’activer ou désactiver le résumé persistant.
- Ajout de deux capteurs d’information financière et de trois rôles de registre.
- Aucun changement du calcul PRI, d’InverterCore, d’Energy Bus, du Machine Learning, du gestionnaire de cycles ou de l’optimiseur économique.
