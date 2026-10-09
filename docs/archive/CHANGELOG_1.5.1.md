# FoxCat Energy 1.5.1 — Stabilisation du dépôt complet

Cette version part directement du dépôt GitHub fourni, dashboard inclus.

## Corrections de fiabilité
- Correction d'un défaut d'exécution dans `coordinator.py` :
  `CONF_GRID_LEGACY_SENSOR` était utilisé sans être importé.
- Le capteur réseau historique signé est maintenant écouté comme télémétrie.
- Une seule source réseau est souveraine pour cadencer le EMS Onduleur :
  capteur export séparé en priorité, legacy uniquement en repli.
- Évite qu'export + legacy puissent provoquer deux décisions RRCR pour une
  même trame physique.
- Ajout de `last_grid_frame_at` dans l'état PRI pour le diagnostic.
- Correction du fallback du régime tarifaire vers `Bi-horaire HP/HC`.
- Synchronisation des versions `manifest.json` et `const.py` à 1.5.1.

## Préservé
- EMS CORE et ses régulations existantes.
- Boiler, fallback et sécurités.
- Gestion machines, cycles protégés et priorité utilisateur.
- HP/HC et dynamique.
- EnergyBus et EMS Onduleur.
- Comptabilité HP/HC par appareil.
- Dashboard intégré au dépôt.
- Le dashboard personnalisé présent dans Home Assistant n'est jamais écrasé
  automatiquement.
