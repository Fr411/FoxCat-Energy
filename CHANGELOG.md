# Changelog — FoxCat Energy V1.7.4

## V1.7.4
- Enregistrement explicite du dashboard utilisateur et fusion avec la dernière version FoxCat.
- La fusion à trois sources conserve les modifications non conflictuelles, signale les conflits et sauvegarde le dashboard courant avant application.

# Changelog — FoxCat Energy V1.7.3

## V1.7.3 (préparation)
- Options des selects mode EMS, politique réseau et régime tarifaire cohérentes avec les valeurs migrées; descriptions et icônes disponibles dans les attributs.
- Menu principal avec choix segmentés, état actif visible et versions moteur/dashboard affichées.
- Templates d’appareils validés avec le catalogue matériel, switches dédiés et actions de désactivation sûres.
- Vue Technique complétée avec paramètres natifs number/switch/time et services de profils JSON, chargement et réinitialisation.
- Versions du dashboard détectées depuis les fichiers disponibles; sauvegarde et rollback, sans écraser un dashboard personnalisé.
- Tests autonomes ajoutés. Aucune release/tag GitHub n’est créée par cette préparation.

# Changelog — FoxCat Energy V1.7.2 Professional

## V1.7.2
- Les sélections initiales et les options de configuration sont maintenant reprises dans les réglages actifs, sans écraser les réglages conservés dans le Store.
- Le comportement EMS ne verrouille plus le régime tarifaire ni la politique réseau.
- Le chemin de lecture des séries tarifaires Day-Ahead est implémenté; les prix Simple et HP/HC restent déterministes et n'utilisent pas les prévisions J+1.
- Les comportements Éco et Confort utilisent le dispatch de stratégie Éco; l'arbitrage boiler Day-Ahead s'applique avec les sources dynamiques, hors Manuel.
- Le Price Analyzer calcule les fenêtres favorables, les pics, les meilleurs créneaux J/J+1, la durée utilisée/restante et les comparaisons avec J-1.
- Tests autonomes ciblés et rapport de validation mis à jour. Les vérifications Home Assistant et matérielles restent requises.

## V1.7.1
- Séparation comportement EMS / source de prix / structure tarifaire / politique réseau.
- Comportements Éco, Confort, Manuel.
- Price Analyzer V2 J/J+1, REACTIVE/PREDICTIVE et granularité native.
- Flexible Load Planner START_NOW / WAIT / CONTINUE / STOP_WHEN_SAFE / USER_CONTROL / SAFETY_OVERRIDE.
- Coordination multi-charges et fenêtres partielles.
- Boiler intégré au Planner avec sécurité thermique conservée.
- Structures Simple / Bi-horaire / Impact.
- Politique réseau Compensation / Injection tarifée / Injection non valorisée / Zéro injection.
- Gestionnaire indépendant des versions de dashboard.
- Dashboard V1.6.160 original conservé.
