# FoxCat Energy

**FoxCat Energy** est une intégration Home Assistant de gestion énergétique résidentielle (EMS). Elle coordonne l'autoconsommation photovoltaïque, le chauffe-eau, les machines, la batterie et le pilotage d'onduleur, selon les sources disponibles, le mode EMS, le tarif et la politique réseau choisis.

| | |
|---|---|
| Version de l'intégration | **1.7.6** |
| Home Assistant minimal | **2025.1.0** |
| Domaine | `foxcat_energy` |
| Langue de configuration | Français |

La version est définie dans [`manifest.json`](custom_components/foxcat_energy/manifest.json). Le détail des changements est dans le [journal des versions](CHANGELOG.md).

## Fonctions

- **Modes EMS** : Éco, Confort et Manuel (le mode Manuel coupe le pilotage automatique, la sécurité thermique reste active).
- **Tarification** : le **contrat** (prix saisis, capteurs ou dynamique) et la **structure du réseau** (mono-horaire, bi-horaire, Impact) sont deux choix indépendants ; toutes les combinaisons sont possibles. Option « Mes prix sont tout compris » pour ne pas compter deux fois réseau, taxes et marge.
- **Comparateur de tarifs** : FoxCat enregistre consommation et prix au quart d'heure (62 jours) et rejoue chaque tarif configuré dessus. Modèles belges prédéfinis (Wallonie, Flandre, Bruxelles) ou tarifs personnalisés en JSON. Comparaison à comportement constant.
- **Coûts réseau et prosumer** : terme capacitaire (forfait bruxellois, pointe mensuelle flamande) et redevance prosumer, appliqués à tous les tarifs comparés.
- **Publication des prix** : une entité (par exemple « prix de demain disponible ») déclenche la relecture des prix, avec un service de relecture optionnel. Les prix de gros ne servent jamais de prix payé.
- **Politique réseau** : compensation, injection tarifée, injection non valorisée ou zéro injection.
- **Solaire et onduleur** : suivi des mesures et pilotage PRI/RRCR lorsque les entités nécessaires sont configurées.
- **Chauffe-eau** : stratégies Éco, Confort, Bihoraire et Dynamique, avec attente du dernier failback en heures creuses.
- **Machines** : gestion de machines ON/OFF extensibles, fenêtres horaires, protection des cycles, phase du réseau par machine.
- **Chauffage** : décalage de consigne selon le surplus solaire et la présence (désactivé par défaut), appliqué à Versatile Thermostat par une automatisation. FoxCat n'écrit jamais dans les `climate.*`.
- **Protection du raccordement** : écrêtage de pointe, délestage des charges élevées, seuil de disjoncteur.
- **Batterie et véhicule électrique** : simulateur désactivé par défaut et sans commande physique ; V2H opt-in.
- **Prévisions et IA** : analyse des prix (Price Analyzer V2), Day-Ahead, planificateur de charges flexibles.
- **Économies** : suivi de ce que FoxCat fait économiser, par jour, mois et année.

Le mode EMS, le régime tarifaire et la politique réseau sont des réglages distincts. Les commandes disponibles dépendent des équipements configurés.

## Installation

### Avec HACS

1. Dans HACS, ouvrez **Intégrations** puis le menu **Dépôts personnalisés**.
2. Ajoutez `https://github.com/Fr411/FoxCat-Energy` avec la catégorie **Intégration**.
3. Installez FoxCat Energy et redémarrez Home Assistant.
4. **Paramètres → Appareils et services → Ajouter une intégration**, puis **FoxCat Energy**.

### Manuelle

Copiez `custom_components/foxcat_energy` dans `/config/custom_components/foxcat_energy`, redémarrez, puis ajoutez l'intégration.

## Configuration

L'installation pose trois questions : **contrat et région**, **réseau**, **prix**. Prévoyez :

- un capteur de puissance réseau signée et sa convention de signe ;
- un capteur de production photovoltaïque ;
- les entités du chauffe-eau, des machines et de l'onduleur à gérer ;
- les prix de votre contrat, saisis à la main ou lus depuis vos capteurs (Luminus, Nord Pool, ENTSO-E, `be_electricity_prices`…).

Tout se règle ensuite dans **Configurer** : le menu compte 7 entrées par tâche, avec un résumé de l'état en tête. Pour la tarification : *Contrat et réseau*, *Coûts réseau et prosumer*, *Publication des prix*. Un avertissement apparaît tant que des modifications ne sont pas enregistrées.

Les entités sont rangées en 10 appareils : Mesures et sources, Tarification, Onduleur, Boiler, Chauffage, Machines, Batterie et VE, Protection, Prévisions et IA, Système.

Avant d'autoriser le pilotage, vérifiez les mesures et les diagnostics, et désactivez les automatisations existantes qui commandent les mêmes équipements.

## Dashboards

FoxCat génère ses dashboards YAML dans `/config/foxcat_energy/` :

- `dashboard.yaml` (tablette / PC) et `dashboardmob1.yaml` (mobile), créés s'ils n'existent pas ; les fichiers existants ne sont jamais écrasés au démarrage ;
- le bouton **Régénérer le dashboard FoxCat** force la régénération, avec sauvegarde `.bak` ;
- les sélecteurs de version tablette et mobile sont indépendants ; les versions sont lues dans `custom_components/foxcat_energy/dashboard/versions/` ;
- la fusion à trois sources conserve vos personnalisations non conflictuelles.

Pour les déclarer dans Home Assistant, fusionnez une fois [`configuration.yaml.snippet`](configuration.yaml.snippet) dans `configuration.yaml` (dashboards `foxcat-energy` et `foxcat-energy2`), puis redémarrez. Ne modifiez pas `.storage/lovelace_dashboards`. Les cartes nécessitent `custom:button-card`, `custom:apexcharts-card` et `card-mod`.

## Cartes et exemples

| Fichier | Contenu |
|---|---|
| [`docs/cartes/vue_couts.yaml`](docs/cartes/vue_couts.yaml) | Vue « Coûts » tablette : tarification, comparateur, coûts réseau, graphiques |
| [`docs/mobile/cartes/vue_couts_mobile.yaml`](docs/mobile/cartes/vue_couts_mobile.yaml) | Même vue, version mobile compacte |
| [`docs/cartes/comparateur_tarifs.yaml`](docs/cartes/comparateur_tarifs.yaml) | Carte markdown simple du comparateur |
| [`docs/automations/etage_decalage_vtherm.yaml`](docs/automations/etage_decalage_vtherm.yaml) | Automatisation du décalage de consigne chauffage |

## Sécurité et limites

FoxCat Energy peut piloter des équipements électriques. Validez capteurs, polarités, actionneurs et limites physiques avant d'activer la régulation, et gardez les protections matérielles en place : le logiciel n'est pas un dispositif de sécurité certifié. Pour revenir en arrière : coupez « Régulation FoxCat active », libérez l'onduleur à 100 %, puis restaurez la version précédente.

Le dépôt est en développement actif. Les tests et simulations ne remplacent pas une validation sur l'installation réelle.

## Dépôt

```text
custom_components/foxcat_energy/   intégration (domain/, runtime/, trading/, dashboard/…)
tests/                             tests unitaires
docs/                              plans, cartes, automatisations, archives par version
trash/                             fichiers obsolètes mis de côté (voir trash/LISEZMOI.md)
CHANGELOG.md                       journal des versions
```

## Licence

Voir [`Licence.md.txt`](Licence.md.txt).
