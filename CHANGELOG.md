# Changelog — FoxCat Energy V1.7.6

## Non publié
- Menu de configuration réorganisé : 7 entrées par tâche, sous-menu Équipements, résumé de l'état en tête de menu et avertissement tant que des modifications ne sont pas enregistrées.
- Formulaires longs regroupés en sections repliables, dans les options et à l'installation; les réglages restent stockés à plat, sans migration.
- Vider un champ d'entité est désormais enregistré; auparavant l'ancienne valeur restait active.
- Modifier ou supprimer sans machine configurée ne ferme plus le menu, ce qui faisait perdre les modifications en attente.
- Une machine refusée conserve les valeurs saisies; libellés manquants ajoutés (détection de cycle, stratégie dynamique, source de réinjection).
- Écrêtage de pointe : tous les réglages du menu sont appliqués par le moteur (phases, base de mesure, seuils, trames, actions, assistance V2H). Les valeurs par défaut conservent le comportement précédent, sauf les deux points ci-dessous.
- Le réarmement reste au moins 5 % sous le déclenchement, ce qui évite les oscillations avec un petit disjoncteur.
- Pendant un délestage, seules les machines marquées délestables sont coupées; les autres restent dans leur état.
- Suppression de `coordinator.py` et `vpp.py` à la racine du composant : ces copies n'étaient chargées par aucun module.

## V1.7.6
- Ajout du mode développeur, des scénarios tarifaires diagnostiques sans effet sur les décisions live et du calcul du seuil disjoncteur.
- V2H physique opt-in avec commande HA configurée explicitement, réserve SoC obligatoire et interverrouillage du chauffe-eau de confort.
- Le Flexible Load Planner V1.7.1 reste seul décideur de `allow_start`; le Day-Ahead historique est informatif.
- Arbitrage virtuel à l'achat/revente tenant compte du spread et du coût d'usure; le ledger physique reste inchangé.
- Tolérance des intégrateurs de télémétrie étendue à une heure et distribution/prix centralisés dans le moteur tarifaire.

# Changelog — FoxCat Energy V1.7.5

## V1.7.5
- Rétablissement de la génération indépendante des dashboards tablette et mobile.
- Configuration validée du simulateur batterie + véhicule électrique, désactivé par défaut et sans commande physique.
- Correction de l’initialisation des capteurs et alignement des versions d’intégration.
- Plafond Day-Ahead fixé à 70 % par défaut; la migration initialise ce nouveau défaut uniquement lorsqu’aucune valeur n’était configurée.

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
