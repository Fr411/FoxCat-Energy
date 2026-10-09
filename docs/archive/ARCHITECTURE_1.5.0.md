# Architecture FoxCat Energy 1.5.0

EMS CORE <-> EnergyBus <-> EMS Onduleur

Le bus transmet immédiatement les intentions. Le EMS Onduleur n'exécute une
commande RRCR qu'à l'arrivée de la prochaine trame réseau.

EMS CORE reste responsable des consommateurs.
EMS Onduleur reste responsable de la puissance PV/RRCR.
Le bus n'est pas décisionnaire.
