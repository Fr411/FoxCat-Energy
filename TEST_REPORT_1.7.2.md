# FoxCat Energy V1.7.2 — État des validations

## Vérifications automatisées

Tests unitaires standards :

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Les tests ciblés couvrent :

- la migration de l'ancien mode Dynamique vers le comportement Éco avec préservation de la source Day-Ahead;
- le dispatch du comportement Confort vers la stratégie de base Éco;
- les états REACTIVE/PREDICTIVE selon la présence de données J+1;
- le plafond de durée des fenêtres favorables, les pics et les meilleurs créneaux.

Compilation sans écrire de bytecode dans le dépôt :

```bash
PYTHONPYCACHEPREFIX=/tmp/foxcat-pycache python -m compileall -q custom_components/foxcat_energy tests
```

Ces vérifications sont ciblées et ne valent pas validation complète de la release.

## Non vérifié

- Démarrage Home Assistant, persistance réelle des Config Flow/Options Flow et registre des entités;
- données Day-Ahead réelles, contrats tarifaires, entités indisponibles et transitions DST;
- commandes physiques et sécurité thermique du boiler;
- PRI/RRCR, InverterCore, ACK/NOK EnergyBus et prises machines;
- rendu du dashboard et tests mobile/tablette/desktop, changement de version et rollback.

Ces points nécessitent un runtime Home Assistant, des données fournisseur réelles ou les équipements physiques. Ne pas les considérer comme validés.
