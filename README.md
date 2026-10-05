# FoxCat Energy 1.7.0

**EMS local pour Home Assistant — énergie, onduleur, charges flexibles, tarification et réseau belge.**

Version actuelle : **1.7.0**  
Base de migration : **1.6.160**  
Fonctionnement : **local dans Home Assistant**

## Architecture 1.7.0

La 1.7.0 sépare quatre notions qui étaient auparavant mélangées :

1. **Comportement EMS** : `Éco`, `Confort`, `Manuel`.
2. **Contrat énergie** : `Fixe / Monohoraire`, `Bi-horaire HP/HC`, `Dynamique`.
3. **Profil distribution / comptage Belgique** : Wallonie, Flandre ou Bruxelles selon le profil choisi.
4. **Politique réseau** : `Injection tarifée`, `Compensation`, `Zéro injection`.

Changer le comportement EMS ne réécrit plus silencieusement le contrat ou la politique réseau.

## Comportements moteur

- **Éco** : applique strictement les règles économiques et reporte davantage les charges flexibles.
- **Confort** : conserve l'optimisation mais assouplit les seuils autorisés par le paramètre `comfort_relaxation_pct`.
- **Manuel** : suspend les décisions automatiques de charge et libère le PRI ; les sécurités physiques restent actives.

## Distribution / comptage Belgique

Profils disponibles :

- Wallonie · Monohoraire ;
- Wallonie · Bihoraire 2026 ;
- Wallonie · Impact ;
- Wallonie · Exclusif nuit (piloté GRD) ;
- Flandre · Standard ;
- Flandre · Capacité ;
- Bruxelles · Monohoraire ;
- Bruxelles · Bihoraire.

Le profil de distribution est indépendant du contrat de fourniture. En Wallonie · Impact, FoxCat distingue `ECO`, `MEDIUM` et `PIC` et peut reporter de nouvelles charges flexibles en période PIC en comportement Éco.

## Boiler = charge flexible universelle

Le Boiler n'est plus attaché à un mode tarifaire particulier. Le même moteur de charge flexible est utilisé avec tous les contrats et profils de comptage.

Ordre de priorité :

1. sécurité thermique ;
2. commande utilisateur ;
3. **surplus solaire suffisant → BOOST jusqu'à la consigne solaire** ;
4. arbitrage du contrat actif ;
5. comportement Éco / Confort ;
6. fallback seulement lorsque l'estimation thermique est suffisamment fiable.

Le BOOST solaire reste indépendant du prix : si le surplus avant charge couvre la résistance, le Boiler peut stocker jusqu'à la consigne boost, typiquement **65 °C**, sous la sécurité absolue configurée.

### Estimateur thermique deux sondes

L'installation peut fournir :

- la sonde **bas / doigt de gant proche résistance** ;
- la sonde **haut / contact sur tête de cuve**.

La sonde basse reste la référence de sécurité mais son poids thermique est réduit pendant et après la chauffe, car la résistance la biaise. La sonde haute est corrigible par offset et sert particulièrement à la tendance et à la détection d'un puisage. FoxCat expose :

- température thermique estimée ;
- confiance de l'estimation ;
- état thermique ;
- détection de puisage ;
- poids appliqué aux deux sondes ;
- énergie manquante et durée estimée de chauffe.

Une simple température sous la consigne ne constitue plus une priorité absolue Day-Ahead.

## Contrat Dynamique

Le planificateur Day-Ahead n'est actif que lorsque le **contrat énergie = Dynamique** et que le comportement n'est pas Manuel.

- seuil favorable : **30 %** par défaut ;
- plafond économique : **65 %** par défaut ;
- Confort peut assouplir le seuil de départ sans modifier le seuil de référence ;
- les plages horaires utilisateur LL / SL / LV restent souveraines ;
- un cycle déjà commencé reste protégé ;
- le planificateur indique la **durée restante du creux favorable actuel**.

Le Boiler peut charger jusqu'à la cible confort sur réseau selon l'arbitrage Dynamic, mais le stockage boost 65 °C reste réservé au solaire suffisant.

## Politique réseau

- **Injection tarifée** : la valeur économique réelle de l'export est utilisée.
- **Compensation** : l'onduleur reste libéré à 100 % selon la règle historique validée.
- **Zéro injection** : le PRI vise une réinjection quasi nulle et ignore la libération liée à un export rémunérateur.

## Dashboard 1.7.0

Une seule vue est exposée comme vue principale : **FoxCat Energy**. Toutes les autres sont des `subview` :

- Énergie ;
- Marché & Réseau ;
- Boiler ;
- Appareils ;
- Onduleur ;
- Technique ;
- Diagnostic.

L'identité visuelle utilise la signature du logo FoxCat : fond sombre, halos **orange solaire** et **cyan énergie**, cartes translucides et profondeur légère. Chaque sous-vue possède une variation de fond liée à sa fonction.

Les cartes tarifaires sont contextuelles :

- aucun bloc Dynamic hors contrat Dynamique ;
- aucun bloc HP/HC hors contrat Bihoraire ;
- le bloc Impact n'apparaît que si `Wallonie · Impact` est sélectionné.

## EMS Configurator

La sous-vue **Technique** devient le configurateur utilisateur. Elle explique et expose :

- comportement EMS ;
- contrat énergie ;
- profil distribution / comptage ;
- politique réseau ;
- réglages Day-Ahead lorsque Dynamic est actif ;
- paramètres Boiler et fiabilité des sondes ;
- maintenance et diagnostic.

La configuration avancée de l'intégration conserve les sources physiques, les machines, les prix et les prévisions.

## Prévisions solaires

Forecast.Solar reste une source déterministe de contexte. Les éléments d'interface et de configuration présentés comme « IA » ont été retirés en 1.7.0. L'apprentissage passif des cycles machines reste disponible sous **Machine Learning** et ne commande directement aucun équipement.

## Anti-régression

Les fichiers suivants sont conservés bit pour bit depuis 1.6.160 :

- `energy_bus.py` ;
- `machine_cycle.py` ;
- `machine_learning.py` ;
- `accounting/manager.py` ;
- `engine/load_guard.py`.

La 1.6.160 reste le point de rollback officiel.

## Installation

Copier `custom_components/foxcat_energy` dans `/config/custom_components/foxcat_energy`, redémarrer Home Assistant, puis recharger l'intégration FoxCat Energy.

Le dashboard client prêt à importer est fourni à la racine :

`homefoxcat_dashboard_client_1.7.0.yaml`

Les anciens fichiers 1.6.x restent présents dans l'archive uniquement comme documentation historique et support de rollback.
