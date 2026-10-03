# Audit anti-régression — FoxCat Energy 1.6.155

Base de comparaison : **FoxCat Energy 1.6.154 Professional**.

- Fonctions/méthodes 1.6.154 : **337**
- Fonctions/méthodes 1.6.155 : **337**
- Ajoutées : **0**
- Supprimées : **0**

## Changement fonctionnel volontaire

- Suppression de l’appel automatique à `async_set_mode(MODE_ECS)` après confirmation de fin solaire.
- La libération de l’onduleur à 100 % est conservée.
- Le mode EMS courant est conservé et la raison de diagnostic l’indique explicitement.

## Fichiers moteurs critiques inchangés

- `custom_components/foxcat_energy/inverter_core.py` : **inchangé**
- `custom_components/foxcat_energy/engine/pri.py` : **inchangé**
- `custom_components/foxcat_energy/energy_bus.py` : **inchangé**
- `custom_components/foxcat_energy/economic_optimizer.py` : **inchangé**
- `custom_components/foxcat_energy/machine_cycle.py` : **inchangé**
- `custom_components/foxcat_energy/machine_learning.py` : **inchangé**
- `custom_components/foxcat_energy/accounting/manager.py` : **inchangé**

## Fonctions ajoutées

- Aucune.

## Fonctions supprimées

- Aucune.

## Conclusion

Le changement est limité à la transition de fin solaire et aux métadonnées/documentation de version. Aucun algorithme PRI ou moteur économique n’est modifié.
