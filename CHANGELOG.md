# Changelog — FoxCat Energy V1.7.6

## Non publié
- Chauffage : optimisation des consignes des PAC air/air (réglage « FoxCat applique la rehausse de consigne »). Nouveau champ « Température de consigne max » par système (16 à 30 °C, 24 °C par défaut). Tant qu'un décalage est accordé, toutes les unités en chauffage d'un système reçoivent la même consigne (moyenne de leurs consignes + décalage, plafonnée par la température max, jamais en dessous de la consigne d'origine) et les unités éteintes sont allumées au même niveau, même si toutes sont éteintes, puisqu'un décalage n'est accordé que si le décalage de consigne est activé (leur consigne d'avant optimisation sert alors de référence). L'état (marche/arrêt) et la consigne de chaque unité sont mémorisés avant la première modification, y compris après un redémarrage, et rétablis dès que l'optimisation n'est plus possible : décalage retombé à 0, régulation ou fonction coupée, réglage retiré, système supprimé ou plus aucune unité de référence en chauffage. Une consigne modifiée à la main devient la nouvelle référence ; une unité éteinte à la main pendant l'optimisation n'est plus rallumée avant la fin du décalage.
- Chauffage : nouveau sous-menu Équipements → Chauffage → « Systèmes de chauffage (pompes à chaleur) ». Chaque système (ajout, modification, suppression) est un groupe extérieur de type PAC air/air, eau/eau ou air/eau, avec son capteur de puissance (obligatoire), son capteur de tension et sa phase L1/L2/L3 (optionnels). Une PAC air/air peut lier jusqu'à 5 climates intérieurs ; pour une PAC eau/eau ou air/eau, seul le groupe extérieur est configuré. Stocké dans l'option `heating_systems_v1`. Rehausse de consigne par système : FoxCat calcule un décalage pour chaque système (surplus partagé entre les groupes, garde de puissance et anti-yoyo propres à chaque groupe) et le publie dans un capteur « Décalage de consigne • nom du système ». Sans capteur « puissance du groupe » dans les réglages, la somme des groupes configurés sert de puissance de groupe. Pour une PAC air/air avec unités intérieures, le réglage « FoxCat applique la rehausse de consigne » (désactivé par défaut) fait régler par FoxCat la consigne des climates en mode chauffage (consigne d'origine + décalage, au pas et dans les bornes de l'unité). La consigne d'origine est mémorisée, même après redémarrage, et restaurée quand le décalage retombe à 0, que la fonction est coupée ou que le système est retiré ; une consigne modifiée à la main devient la nouvelle consigne d'origine. Sans ce réglage, FoxCat n'écrit toujours jamais dans les `climate.*`.
- Configurateur de tarification : le contrat (prix saisis, capteurs ou dynamique) et la structure du réseau (mono-horaire, bi-horaire, Impact) sont deux choix indépendants, à l'installation comme dans les options. Toutes les combinaisons sont possibles, dont Impact avec un contrat fixe et bi-horaire avec un contrat dynamique. Installation en trois questions (contrat et région, réseau, prix) ; les prix d'un contrat fixe peuvent être saisis à la main au lieu d'exiger des capteurs. Nouvel écran « Contrat et réseau » dans Tarification : il écrit ensemble la source, la structure, le régime et le profil de distribution pour qu'ils restent cohérents.
- Case « Mes prix sont tout compris » (réglage `price_is_all_in`, décochée par défaut) : quand le prix lu contient déjà réseau, taxes et marge, FoxCat n'ajoute plus de complément de distribution, ce qui évitait un double comptage. Les installations existantes ne changent pas.
- Les formulaires ne préremplissent plus d'entités d'un fournisseur précis (Luminus) : seules les entités choisies par l'utilisateur sont enregistrées. Les prix HP et HC d'un contrat fixe, jusque-là sans réglage, sont désormais saisissables (`tariff_hp_price_eur_kwh`, `tariff_hc_price_eur_kwh`).
- Nouveau comparateur de tarifs : FoxCat enregistre la consommation et les prix lus au quart d'heure (stockage séparé, 62 jours) et rejoue chaque tarif configuré dessus. Capteurs « Comparateur de tarifs • Aujourd'hui / Ce mois » : tarif le moins cher, coût net par tarif et écart avec le tarif actuel. Modèles belges prédéfinis (Wallonie mono, bi-horaire 2026, Impact ; Flandre capacitaire ; Bruxelles forfait), tarifs personnalisés en JSON, préchargement des modèles selon la région. Comparaison à comportement constant : le pilotage de FoxCat n'est pas rejoué.
- Coûts réseau : nouvel écran Tarification → Coûts réseau et prosumer, rempli par l'installateur : terme capacitaire (forfait annuel à Bruxelles, pointe mensuelle au quart d'heure en Flandre, avec minimum facturé) et redevance prosumer annuelle. Ces coûts dépendent du réseau, pas du fournisseur : le comparateur les applique à tous les tarifs, donc l'écart ne reflète que le prix de l'énergie. À l'installation, la région Flandre ou Bruxelles propose les moyennes du guide des tarifs, à remplacer par les montants de la facture. Les entités de l'intégration de prix (coût capacitaire, pointe mensuelle, coût prosumer) sont facultatives et servent de contrôle, sans être additionnées. Nouveau capteur « Coûts réseau • Ce mois ». Carte d'exemple : `docs/cartes/comparateur_tarifs.yaml`. Les modèles « Flandre • Capacitaire » et « Bruxelles • Forfait » sont retirés des tarifs : ce n'étaient pas des tarifs.
- Publication des prix : nouvel écran Tarification → Publication des prix. Une entité (par exemple « prix de demain disponible » de Nord Pool) déclenche la relecture des prix, avec un service de relecture optionnel (par exemple `be_electricity_prices.refresh`), au plus une fois toutes les 10 minutes. Les prix de gros ne servent jamais de prix payé.
- Appareils Home Assistant regroupés : de 15 appareils à 10, avec les mêmes noms que le menu d'options. Mesures et sources, Tarification, Onduleur, Boiler, Chauffage, Machines, Batterie et VE, Protection, Prévisions et IA, Système. Les deux appareils « IA » en double sont fusionnés ; le chauffage et la protection du raccordement (disjoncteur, délestage) sortent de « EMS » ; Énergie, Métronome et Sources sont réunis ; Energy Bus, Diagnostic et le cœur EMS vont dans « Système ». Seul le rattachement aux appareils change : les `entity_id` et `unique_id` existants sont conservés, donc dashboard et automatisations continuent de fonctionner. Les anciens appareils vidés sont supprimés au démarrage. Les appareils renommés à la main dans Home Assistant repartent avec le nom FoxCat. Libellés du menu d'options alignés (Mesures et sources, Protection, Prévisions et IA, Batterie et VE).
- Chauffage : FoxCat crée désormais toutes les entités nécessaires à l'automatisation du thermostat, sans helper à créer à la main : `number` « Chauffage • Décalage appliqué aux presets » (conservé au redémarrage, absent des profils et de « Réinitialiser les réglages »), `binary_sensor` « Chauffage • Décalage actif », capteurs « Pas accordés » et « Surplus calculé ». Le menu Équipements → Chauffage devient un sous-menu : « Réglages du décalage de consigne » et « Entités créées par FoxCat », qui affiche l'`entity_id` réel de chaque entité. Automatisation d'exemple lisant les réglages FoxCat : `docs/automations/etage_decalage_vtherm.yaml`.
- Nouveau : décalage de consigne chauffage (désactivé par défaut). FoxCat calcule un décalage en °C (0 à 2 °C par défaut, par pas de 0,5 °C) selon le surplus solaire et la présence, et le publie dans le capteur « Chauffage • Décalage de consigne » (`foxcat_chauffage_decalage_consigne`), avec un capteur « Chauffage • Statut » qui donne la raison. Une automatisation Home Assistant l'applique aux presets Versatile Thermostat : FoxCat n'écrit jamais dans les `climate.*` ni dans les `number.*`. Anti-yoyo (300 s avant toute augmentation), hystérésis à 60 % du seuil, baisse immédiate si l'import dépasse 300 W, garde sur la puissance du groupe de clim. Réglages dans Équipements → Chauffage. L'état est en mémoire et repart à 0 au redémarrage.
- Boiler en heures creuses : il attend désormais le dernier failback avant de chauffer sur le réseau, pour laisser la priorité au solaire (Éco, Confort, Bihoraire). Nouvel interrupteur « Boiler : attendre le dernier failback en HC » (actif par défaut) et réglage « Marge de sécurité failback boiler » (30 min par défaut). Interrupteur coupé = ancien comportement. Le mode Dynamique est inchangé.
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
