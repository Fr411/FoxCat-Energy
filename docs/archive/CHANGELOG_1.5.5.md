# FoxCat Energy 1.5.5 — PRI prédictif à palier optimal

## Principe
Le métronome réseau reste responsable de la fraîcheur et de la synchronisation des mesures. Il ne détermine plus la vitesse de déplacement du PRI.

À chaque battement valide, `InverterCore` simule directement les 11 paliers RRCR disponibles (0, 10, 20, …, 100 %) et choisit le palier qui donne le meilleur compromis réseau.

## Calcul
- Charge maison estimée par bilan physique de la trame : `PV + import - export`.
- Puissance PV cible : `charge maison estimée - import cible`.
- Simulation du réseau attendu pour chaque palier de 10 %.
- Pénalité forte si la réinjection dépasse le maximum configuré ou si l'import dépasse sa limite.
- Utilisation des poids PRI import/réinjection déjà configurables.
- Marge de score conservée pour éviter les commutations inutiles dans la zone maîtrisée.

## Comportement
- Une forte réinjection peut désormais produire directement une commande `90 % -> 20 %` si 20 % est le meilleur palier calculé.
- Le moteur ne doit plus attendre plusieurs battements pour parcourir 90, 80, 70, etc.
- Si le PV est sous son plafond actuel, une remontée du PRI n'est pas considérée comme pouvant créer davantage de solaire.
- Si le PV est réellement bridé, le moteur peut libérer directement le palier requis par la charge maison.
- La commande reste exclusivement sur les paliers RRCR existants par multiples de 10 %.

## Diagnostics ajoutés
- Charge maison estimée par bilan réseau.
- Puissance PV cible PRI.
- Import réseau prévu au palier cible.
- Réinjection prévue au palier cible.
- Score du palier actuel et score du palier cible alimentés par le moteur actif.

## Conservé
- Métronome principal/fallback de la 1.5.4.
- Gel PRI si les sources de synchronisation sont périmées.
- ACK RRCR et validation N+1.
- EnergyBus.
- CORE EMS, boiler, machines, tarification et protections existantes.
