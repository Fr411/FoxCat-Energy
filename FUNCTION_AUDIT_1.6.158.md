# FoxCat Energy 1.6.158 — Audit des fonctions

Inventaire AST du composant :

- 1.6.157 : **348 fonctions/méthodes**
- 1.6.158 : **352 fonctions/méthodes**
- ajoutées : **4**
- supprimée : **0**

Ajouts :

1. `accounting/manager.py::EnergyAccounting._add_signed`
2. `sensor.py::FoxCatTariffCurveSensor.__init__`
3. `sensor.py::FoxCatTariffCurveSensor.native_value`
4. `sensor.py::FoxCatTariffCurveSensor.extra_state_attributes`

La nouvelle entité **Courbe tarifaire FoxCat** expose au dashboard exactement les mêmes points achat/réinjection que ceux utilisés par le moteur économique. Aucun moteur sanctuarisé n'a perdu de fonction.
