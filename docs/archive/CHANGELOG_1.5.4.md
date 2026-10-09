# FoxCat Energy 1.5.4 — Métronome réseau synchronisé

## Objectif

Fiabiliser la cadence EMS/PRI lorsque le capteur réseau republie une valeur identique et qu'aucun `state_changed` classique n'est généré.

## Changements

- Nouveau sélecteur `metronome_sensor` dans **Mesures principales**.
  - Smappee consommation réseau est recommandé comme capteur maître.
  - Pour une configuration 1.5.3 existante, le capteur d'import réseau reste utilisé automatiquement tant que le nouveau choix n'a pas été enregistré.
- Nouveau sélecteur `metronome_fallback_sensor`.
  - Le capteur de secours reste chaud mais ne cadence pas tant que le principal est frais.
  - Il prend automatiquement la main si le principal devient muet.
- Métronome interne par défaut à 30 s.
  - Une publication physique resynchronise le battement.
  - Les republications identiques sont détectées via `state_reported`/`last_reported` lorsque Home Assistant le permet.
  - Un watchdog interne vérifie la fraîcheur toutes les 2 s sans créer de seconde décision PRI.
- Un battement valide déclenche une acquisition CORE puis au maximum une décision PRI.
- Anti-double-battement pour les grappes de publications Smappee quasi simultanées.
- Si principal et secours sont périmés, les décisions sont gelées : aucune régulation sur mesures anciennes.
- Les anciens événements import/export restent disponibles pour la télémétrie mais ne cadencent plus le PRI lorsque le métronome est actif.

## Diagnostics ajoutés

- Statut métronome réseau
- Source métronome réseau
- Capteur actif du métronome
- Dernier battement métronome
- Compteur de battements
- Période du métronome
- Diagnostic métronome réseau

## Réglages exposés

- Période métronome réseau : 30 s par défaut
- Délai perte métronome principal : 45 s par défaut
- Délai perte capteur de secours : 90 s par défaut

## Sécurité

Aucune logique PRI, RRCR, boiler, machine, tarifaire ou EMS existante n'a été supprimée. La modification porte sur la cadence et la synchronisation des acquisitions/décisions.
