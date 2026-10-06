# FoxCat Energy V1.7.1 Professional

EMS local Home Assistant basé exclusivement sur la baseline V1.6.160 fournie.

## Architecture
- EMS Core : économie, charges et coordination.
- InverterCore : PV / PRI / RRCR.
- EnergyBus : intentions, capacités et ACK/NOK.
- BoilerManager : thermique et sécurité.
- MachineCycleManager : protection des cycles.
- Flexible Load Planner : START NOW / WAIT et planification.

## Tarification
Les dimensions sont indépendantes :
- source : Contractuelle / fixe, Variable HA, Dynamique Day-Ahead ;
- structure : Simple, Bi-horaire, Impact ;
- politique : Compensation, Injection tarifée, Injection non valorisée, Zéro injection.

Price Analyzer et optimisation J/J+1 ne s'activent que pour la source Dynamique Day-Ahead.

## Installation
Copier `custom_components/foxcat_energy` dans le répertoire `custom_components` de Home Assistant puis redémarrer Home Assistant.

## Validation
Exécuter les tests autonomes avec `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`. Ils vérifient actuellement la migration du mode Dynamique historique, le dispatch Éco/Confort et les sorties principales de l'analyseur tarifaire (fenêtres, pics et disponibilité J+1). La compilation Python sans artefacts dans le dépôt peut être vérifiée avec `PYTHONPYCACHEPREFIX=/tmp/foxcat-pycache python -m compileall -q custom_components/foxcat_energy tests`.

La validation finale dans Home Assistant, l'interface frontend et avec les équipements physiques reste nécessaire avant mise en production. Ces tests unitaires ne valident pas les commandes physiques, l'ACK EnergyBus/PRI, ni les prix réels fournis par une intégration.

Les valeurs EMS enregistrées dans le flux initial alimentent les réglages au premier démarrage. Par la suite, les choix explicites de l'Options Flow priment sur les réglages persistés; les modifications faites par les entités restent conservées tant qu'elles ne sont pas remplacées par une option. Le comportement EMS ne verrouille plus la structure tarifaire ni la politique réseau.
