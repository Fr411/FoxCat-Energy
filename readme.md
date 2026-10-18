# FoxCat Energy

**FoxCat Energy** est une intégration Home Assistant de gestion énergétique résidentielle (EMS). Elle coordonne l’autoconsommation photovoltaïque, le chauffe-eau, les machines configurées et le pilotage d’onduleur, selon les sources disponibles, le mode EMS, le tarif et la politique réseau choisis.

| | |
|---|---|
| Version de l’intégration | **1.7.5** |
| Home Assistant minimal | **2025.1.0** |
| Domaine | `foxcat_energy` |
| Langue de configuration | Français |

La version de l’intégration est définie dans [`manifest.json`](custom_components/foxcat_energy/manifest.json). Consultez le [journal des versions](CHANGELOG.md) pour le détail des changements.

## Fonctions

- **Modes EMS** : Éco, Confort et Manuel.
- **Tarification** : mono-horaire, HP/HC ou dynamique Day-Ahead, avec une structure de distribution configurable.
- **Politique réseau** : compensation, injection tarifée, injection non valorisée ou zéro injection.
- **Énergie solaire et onduleur** : suivi des mesures et pilotage PRI/RRCR lorsque l’installation et les entités nécessaires sont configurées.
- **Chauffe-eau et machines** : stratégies du boiler et gestion de machines ON/OFF extensibles, avec horaires et protection des cycles.
- **Charges élevées** : délestage configurable pour suspendre certaines charges, dans le respect des cycles protégés.
- **Analyse et planification** : analyse des prix et planification des charges flexibles selon les paramètres disponibles.
- **Diagnostics et dashboards** : entités de suivi, diagnostics de l’intégration et dashboards FoxCat générés à l’installation.

Le mode EMS, le régime tarifaire et la politique réseau sont des réglages distincts. Les commandes disponibles dépendent des équipements, entités et paramètres configurés.

## Installation

### Avec HACS

1. Dans HACS, ouvrez **Intégrations** puis le menu **Dépôts personnalisés**.
2. Ajoutez `https://github.com/Fr411/FoxCat-Energy` avec la catégorie **Intégration**.
3. Installez FoxCat Energy et redémarrez Home Assistant.
4. Dans **Paramètres → Appareils et services → Ajouter une intégration**, recherchez **FoxCat Energy**.

### Installation manuelle

Copiez le dossier `custom_components/foxcat_energy` dans `/config/custom_components/foxcat_energy`, puis redémarrez Home Assistant. Ajoutez ensuite l’intégration depuis **Paramètres → Appareils et services**.

## Configuration initiale

Le flux de configuration demande d’abord la famille tarifaire et sa structure, puis les sources énergétiques et les équipements. Prévoyez notamment :

- un capteur de puissance réseau signée et sa convention de signe ;
- un capteur de production photovoltaïque ;
- les entités du chauffe-eau, des machines et de l’onduleur que vous souhaitez gérer ;
- les entités tarifaires correspondant au régime sélectionné.

Les détails tarifaires et les réglages peuvent être ajustés dans les options de l’intégration. Vérifiez les mesures et les diagnostics avant d’autoriser le pilotage automatique. Désactivez les automatisations existantes qui commanderaient les mêmes équipements afin d’éviter des commandes concurrentes.

## Batterie et véhicule électrique virtuels

La simulation de batterie domestique et de véhicule électrique est **désactivée par défaut**. Lorsqu’elle est activée, elle reste en lecture seule : les équipements virtuels ne commandent aucun appareil physique. Les valeurs simulées doivent être distinguées des mesures réelles ; elles ne remplacent pas le suivi d’une batterie ou d’un véhicule réels.

## Dashboards

FoxCat peut générer ses dashboards YAML dans le dossier `/config/foxcat_energy/`. Les dashboards existants ne sont pas remplacés automatiquement au démarrage. Leur déclaration comme dashboards Lovelace YAML dans Home Assistant peut nécessiter une configuration dédiée ; voir [`configuration.yaml.snippet`](configuration.yaml.snippet).

## Sécurité et limites

FoxCat Energy pilote potentiellement des équipements électriques. Validez les capteurs, polarités, actionneurs et limites physiques de votre installation avant d’activer la régulation. Les protections matérielles et sécurités Home Assistant doivent rester en place ; ne considérez pas le logiciel comme un dispositif de sécurité certifié.

Le dépôt est en développement actif. Les résultats de simulation ou les tests logiciels ne remplacent pas une validation sur l’installation réelle.

## Documentation

- [Journal des versions](CHANGELOG.md)
- [Installation et options des dashboards](README-INSTALL.md)
- [Installation de l’interface Premium](PREMIUM_UI_INSTALL.md)
- [Code de l’intégration](custom_components/foxcat_energy/)
