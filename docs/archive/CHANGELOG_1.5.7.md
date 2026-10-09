# FoxCat Energy 1.5.7 — inventaire matériel informatif

## Inventaire matériel Home Assistant

- Ajout d'un appareil `FoxCat Energy – Matériel installé`.
- Quatre sélecteurs persistants et purement informatifs :
  - `Matériel • Marque onduleur`
  - `Matériel • Modèle onduleur`
  - `Matériel • Système de mesure principal`
  - `Matériel • Modèle / interface de mesure`
- Catalogue onduleur : 50 fabricants avec familles/modèles usuels.
- SolarEdge est préconfiguré sur `SE4K`.
- Catalogue mesure : Smappee (Infinity, Genius, Connect...), Shelly, P1/P2, HomeWizard,
  Tibber, Eastron, Carlo Gavazzi, Victron, compteurs constructeurs, ESPHome, Modbus,
  MQTT et Home Assistant calculé.
- Le modèle proposé dépend automatiquement de la marque/famille sélectionnée.
- `Autre / Non répertorié` est toujours disponible.
- Deux capteurs de synthèse exposent le matériel sélectionné.
- Règle stricte : ces métadonnées ne sont référencées par aucun algorithme PRI, CORE,
  boiler, tarification ou délestage. Elles ne modifient aucun seuil ni coefficient.

