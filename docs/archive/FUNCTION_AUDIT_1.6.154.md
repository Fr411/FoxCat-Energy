# Audit anti-régression — FoxCat Energy 1.6.154

Base comparée : **FoxCat Energy 1.6.153 originale**.

## Résumé

- Fonctions/méthodes 1.6.153 : **331**
- Fonctions/méthodes 1.6.154 : **337**
- Ajoutées : **6**
- Supprimées : **0**

## Fonctions ajoutées

- `config_flow.py :: FoxCatEnergyConfigFlow.async_step_ia`
- `config_flow.py :: FoxCatEnergyOptionsFlow.async_step_ems_core`
- `config_flow.py :: FoxCatEnergyOptionsFlow.async_step_ia`
- `config_flow.py :: FoxCatEnergyOptionsFlow.async_step_machine_learning`
- `config_flow.py :: FoxCatEnergyOptionsFlow.async_step_machine_learning_info`
- `config_flow.py :: FoxCatEnergyOptionsFlow.async_step_pricing_dynamic`

## Fonctions supprimées

- **Aucune.**

## Moteurs critiques gelés

- `inverter_core.py` : **inchangé**
- `engine/pri.py` : **inchangé**
- `energy_bus.py` : **inchangé**
- `economic_optimizer.py` : **inchangé**
- `machine_cycle.py` : **inchangé**
- `machine_learning.py` : **inchangé**
- `accounting/manager.py` : **inchangé**

## Modifications métier volontairement autorisées

- `engine/models.py` : ajout des valeurs de température de sécurité Boiler et puissance physique onduleur au snapshot.
- `engine/modes/eco.py`, `dynamic.py`, `ecs_solar.py` : les contrôles de sécurité thermique utilisent désormais la température de sécurité Résistance quand elle est disponible.
- `coordinator.py` : sélection de la sonde Résistance comme sécurité prioritaire, fallback sur la sonde Boiler historique, et lecture contextuelle de la puissance onduleur.
- Aucune modification de l’algorithme PRI, d’InverterCore, d’Energy Bus, du comparateur économique, de MachineCycleManager ou du moteur Machine Learning.

## Fichiers de code/configuration modifiés

