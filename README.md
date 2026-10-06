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
Les tests autonomes livrés dans `tests/run_v171_tests.py` couvrent les fonctions économiques et de sécurité. La validation finale Home Assistant réel, UI frontend et équipements physiques reste nécessaire avant mise en production.
