# FoxCat Energy 1.6.150 — Cadencement réseau souverain et cœurs indépendants

## Objectif

Supprimer toute possibilité de trame énergétique vieillissante ou bloquée derrière une commande physique. Chaque publication réelle du capteur réseau cadence désormais simultanément EMS Core et Onduleur Core sur le même snapshot énergétique.

## Changements principaux

- Chaque publication réelle du capteur réseau principal crée immédiatement une nouvelle trame.
- Suppression de la fenêtre de 30 s comme cadence de décision : le Métronome devient uniquement un Watchdog de fraîcheur/fallback.
- EMS Core et Onduleur Core reçoivent le même numéro de trame, le même timestamp et le même snapshot.
- Les deux cœurs fonctionnent dans des tasks et verrous indépendants.
- Energy Bus transporte maintenant les décisions dans les deux sens avec ACK/NOK.
- Les messages ACK indiquent explicitement l'émetteur et le destinataire.
- Une trame Energy Bus mémorise réseau, PV, maison, import/export, Boiler, machines, mode EMS et politique réseau.
- Le PRI calcule sa décision immédiatement sur chaque publication.
- La commande RRCR est déplacée dans un worker physique séparé : une commutation ne bloque jamais la décision de la trame suivante.
- Le worker RRCR converge toujours vers la dernière cible demandée et ne constitue pas une file de vieilles consignes.
- Les appels Home Assistant du Boiler sont exécutés dans un worker séparé avec timeout.
- EMS Core ne reste donc plus bloqué sur une commande Climate.
- Le délestage demande la libération PRI via Energy Bus/worker sans bloquer EMS Core.
- Un import réseau au-dessus de l'enveloppe autorise désormais une remontée immédiate du PRI, même si le PV n'est pas formellement détecté au plafond actuel.
- Le fallback ne fabrique pas de trames artificielles : une trame fallback existe uniquement sur publication réelle du capteur de secours.
- Le Watchdog ferme explicitement toute trame restée PENDING anormalement longtemps au lieu de la laisser vieillir silencieusement.

## Diagnostics ajoutés

- Statut de la trame côté EMS Core.
- Statut de la trame côté Onduleur Core.
- Nombre de trames traitées par EMS Core.
- Nombre de trames traitées par Onduleur Core.
- Source/cible/action du dernier message Energy Bus.
- Statut et cible du worker RRCR.

## Compatibilité

Les fonctions historiques de 1.6.1-101 sont conservées. La voie legacy sans capteur Métronome explicite cadence également les deux cœurs sur la même publication réseau.
