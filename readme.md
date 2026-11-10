# FoxCat Energy

**FoxCat Energy** est une intégration Home Assistant de gestion énergétique résidentielle (EMS). À partir de deux mesures (puissance réseau signée et production photovoltaïque), elle décide en continu de chauffer ou non le chauffe-eau, d'autoriser ou non les machines, et de limiter ou non la puissance de l'onduleur, puis vérifie que ses ordres ont réellement eu l'effet attendu.

| | |
|---|---|
| Version | **1.7.6** (voir [`manifest.json`](custom_components/foxcat_energy/manifest.json)) |
| Home Assistant minimal | **2025.1.0** |
| Domaine | `foxcat_energy` |
| Type d'intégration | `local_push`, configuration par l'interface (`config_flow`), aucune dépendance externe |
| Langue | Français uniquement |
| Instances | Une seule installation par Home Assistant |

> **Sécurité.** FoxCat commande des équipements électriques (chauffe-eau, prises, onduleur). Ce n'est pas un dispositif de sécurité certifié : les protections matérielles de l'installation doivent rester en place. La régulation est **désactivée par défaut** (`Régulation FoxCat active` = OFF) ; validez les mesures et les diagnostics avant de l'activer.

## Sommaire

1. [Principe de fonctionnement](#1-principe-de-fonctionnement)
2. [Les trois réglages qui définissent le comportement](#2-les-trois-réglages-qui-définissent-le-comportement)
3. [Le boiler (chauffe-eau)](#3-le-boiler-chauffe-eau)
4. [L'onduleur et le PRI](#4-londuleur-et-le-pri)
5. [Machines](#5-machines)
6. [Protection du raccordement (écrêtage de pointe)](#6-protection-du-raccordement-écrêtage-de-pointe)
7. [IA, prévisions solaires et batterie / VE virtuels](#7-ia-prévisions-solaires-et-batterie--ve-virtuels)
8. [Installation](#8-installation)
9. [Configuration](#9-configuration)
10. [Entités, services et dashboards](#10-entités-services-et-dashboards)
11. [Valeurs par défaut](#11-valeurs-par-défaut)
12. [Limites et points à connaître](#12-limites-et-points-à-connaître)
13. [Développement et tests](#13-développement-et-tests)

---

## 1. Principe de fonctionnement

### Un cycle en trois phases

Le moteur travaille par trames. Chaque nouvelle mesure de puissance réseau signée (le « métronome ») fait avancer un cycle :

| Phase | Rôle |
|---|---|
| `ACQUISITION` | Lecture des mesures et mémorisation de la trame de référence `T0`. |
| `DECISION` | Nouvelle trame comparée à `T0`. Si la puissance réseau a varié de plus de `stability_tolerance_w` (500 W par défaut), la décision est suspendue et le cycle repart de zéro. Sinon le mode, la tarification et les sécurités produisent une intention. |
| `WAIT_ACK` | Attente de la confirmation de l'ordre, puis contrôle de son effet sur la trame suivante. |

Une décision n'est donc prise que sur des mesures stables, et un ordre n'est considéré comme réussi qu'une fois son effet constaté.

### Sources de mesure

- **Puissance réseau signée** : obligatoire. Elle cadence le moteur. La convention de signe est réglable (`import_positive` ou `export_positive`).
- **Production photovoltaïque** : obligatoire. La consommation de la maison est déduite des deux mesures.
- **Puissance réseau de secours** : optionnelle, utilisée seulement si la source principale n'est plus fraîche (délais de perte réglables : 45 s pour la principale, 90 s pour le secours).

### Priorités

Pour le boiler, dans l'ordre : écrêtage de pointe actif, ordres manuels de l'utilisateur, interverrouillage V2H, puis stratégie du mode (sécurité thermique, solaire en priorité, puis arbitrage tarifaire). Le mode **Manuel** suspend toute stratégie automatique mais conserve les sécurités.

---

## 2. Les trois réglages qui définissent le comportement

Le comportement de FoxCat dépend de trois réglages **indépendants**.

### 2.1 Mode EMS

Sélecteur `Mode` : **Éco**, **Confort** ou **Manuel**.

- **Éco** et **Confort** exécutent aujourd'hui la même stratégie boiler (voir [§12](#12-limites-et-points-à-connaître)).
- **Manuel** : aucune décision automatique sur le boiler, le PRI et les prises machines. Mesures, journalisation et sécurités thermiques restent actives.

Les anciens modes (Bihoraire, Dynamique, ECS solaire, Zéro injection, etc.) sont convertis automatiquement en **Éco** à la migration ; le contrat et la politique réseau portent désormais cette information.

### 2.2 Tarification

Trois sous-réglages :

**Source de prix** (`price_source`) :

| Valeur | Usage |
|---|---|
| Contractuelle / fixe | Prix saisis dans la configuration. |
| Variable via entités Home Assistant | Prix lus depuis des entités (par défaut). |
| Intégration externe | Prix fournis par une intégration tierce. |
| Dynamique Day-Ahead | Courbe de prix horaire (aujourd'hui / demain). |

**Structure** (`tariff_structure`) : Simple, Bi-horaire (HP/HC), Impact.
**Profil de distribution** : Simple, Bi-horaire (jour / nuit), Impact. C'est une couche indépendante du contrat.

Le régime effectif (`Régime tarifaire`) est dérivé de ces réglages : *Dynamique* si la source est Day-Ahead ou une intégration externe, *Bi-horaire (HP/HC)* si la structure est Bi-horaire, *Mono-horaire* sinon.

**Heures pleines / creuses par défaut** (modifiables) : HP de 07:00 à 11:00 et de 17:00 à 22:00 ; toutes les autres heures sont creuses.

**Profil Impact** (périodes par défaut) : ECO de 01:00 à 07:00 et de 11:00 à 17:00, PIC de 17:00 à 22:00, MEDIUM le reste du temps.

### 2.3 Politique réseau

Sélecteur `Politique réseau` (`network_policy`) : décrit ce que l'injection sur le réseau vaut pour vous.

| Politique | Effet sur l'onduleur |
|---|---|
| **Compensation** (défaut) | Onduleur toujours libéré à 100 %. Le réseau sert de tampon. |
| **Injection tarifée** | FoxCat simule tous les paliers du PRI et choisit le meilleur compromis import/export. |
| **Injection non valorisée** | Même moteur de simulation des paliers, avec une injection sans valeur. |
| **Zéro injection** | Même moteur de simulation des paliers, avec pour objectif de ne pas réinjecter. |

Quelle que soit la politique, si le prix de réinjection est strictement positif, l'onduleur est libéré à 100 % : une production qui a de la valeur n'est jamais bridée.

---

## 3. Le boiler (chauffe-eau)

### 3.1 Température et paliers

| Réglage | Défaut | Rôle |
|---|---|---|
| Température de reprise (`boiler_temp_start_c`) | 43 °C | Sous ce seuil, une chauffe réseau est justifiée. |
| Température de confort (`boiler_temp_normal_c`) | 45 °C | Cible de la chauffe normale (`CHAUFFE_45`). |
| Température de boost (`boiler_temp_boost_c`) | 65 °C | Cible du stockage solaire (`BOOST_65`). |
| Sécurité (`boiler_temp_safety_c`) | 68 °C | Au-delà, toute chauffe est interdite et un arrêt est demandé. |
| Puissance (`boiler_power_w`) | 1800 W | Sert à calculer la couverture solaire. |
| Cycle minimum (`boiler_cycle_min_s`) | 120 s | Durée minimale d'une chauffe engagée. |

**Règle absolue : le boost à 65 °C est exclusivement solaire.** Le réseau ne chauffe jamais au-delà du confort.

Le boiler est piloté par une entité `climate` (consigne et mode `heat`). Une entité de température de référence est obligatoire ; une sonde de résistance (sécurité), un capteur de puissance et un état physique sont optionnels et recommandés.

### 3.2 Stratégie Éco / Confort (tarif mono ou bi-horaire)

Ordre d'évaluation (le premier cas qui s'applique l'emporte) :

1. Boiler désactivé dans FoxCat, sécurité thermique atteinte, ou 65 °C atteint : **arrêt**.
2. En heures pleines, boiler allumé et import réseau supérieur à 50 W : **arrêt** (aucun achat HP pour le boiler).
3. Cycle minimum en cours : chauffe maintenue.
4. Boost solaire déjà engagé : maintenu tant qu'il n'y a pas d'import (> 50 W) et que le soleil produit.
5. **Surplus solaire** (couverture ≥ 100 % de la puissance du boiler sur deux trames consécutives) : chauffe à 45 °C puis, une fois le confort atteint, boost vers 65 °C.
6. **Heures creuses** : voir ci-dessous.
7. Boiler allumé et 45 °C atteints sans surplus : arrêt.

### 3.3 Heures creuses : attendre le dernier failback

Si `Boiler autorisé en heures creuses` est activé, le boiler peut chauffer sur le réseau en heures creuses. Pour laisser une chance au solaire, **FoxCat ne démarre pas dès l'ouverture des heures creuses** : il attend le **dernier départ possible** (« failback »).

- Le failback est le moment limite à partir duquel il faut chauffer pour atteindre 45 °C avant la fin de la plage creuse (retour des heures pleines), en tenant compte :
  - de la perte thermique (0,5 °C par heure) ;
  - de la vitesse de chauffe (10 °C par heure) ;
  - d'une **marge de sécurité** (`Marge de sécurité failback boiler`, 30 min par défaut, de 0 à 180 min).
- Si le solaire arrive avant ce moment, il prend la main (règle 5 ci-dessus).
- Si le boiler est déjà en train de chauffer, il continue jusqu'au confort.
- Le démarrage réseau en heures creuses n'a lieu que si la température est sous le seuil de reprise (43 °C).
- L'interrupteur **`Boiler : attendre le dernier failback en HC`** (actif par défaut) permet de revenir à l'ancien comportement (démarrage dès l'ouverture des heures creuses) en le coupant.

### 3.4 Stratégie Dynamique (Day-Ahead)

Quand le régime est Dynamique, une branche dédiée remplace la stratégie précédente. FoxCat positionne le prix courant dans la courbe du jour (position en %, 0 % = le moins cher) :

| Position du prix | Comportement |
|---|---|
| ≤ seuil favorable (`dynamic_favorable_position_pct`, 30 %) | Chauffe jusqu'à 45 °C si la température est sous le confort. |
| Entre 30 % et le plafond (`dynamic_high_position_pct`, 70 %) | Chauffe jusqu'à 45 °C seulement si la température est sous la reprise (43 °C), ou si une fenêtre Day-Ahead réservée est active. |
| > plafond | Aucune nouvelle chauffe réseau. |

Si la position du prix est indisponible, le boost réseau est interdit : au mieux, le confort à 45 °C est maintenu. Le surplus solaire reste prioritaire et n'est jamais bloqué par le prix. Si le prix devient négatif, FoxCat peut charger le boiler sur le réseau (interrupteur `Charge réseau si prix dynamique négatif`, seuil réglable).

### 3.5 Autres règles qui peuvent interrompre ou différer le boiler

- **Ordres utilisateur** (boutons *Démarrage utilisateur*, *Arrêt utilisateur*, *Retour automatique EMS*) : prioritaires sur la stratégie, sauf sécurité thermique.
- **Cycle machine protégé** : le boiler n'est pas interdit par principe. Hors politique Compensation, il est différé si le surplus réel, après la machine, ne couvre pas sa puissance (validation sur deux trames).
- **Écrêtage de pointe** : arrêt du boiler (voir [§6](#6-protection-du-raccordement-écrêtage-de-pointe)).
- **Interverrouillage V2H** : chauffe de confort suspendue pendant une décharge du véhicule.

---

## 4. L'onduleur et le PRI

FoxCat limite la puissance photovoltaïque via les quatre entrées **RRCR** (`L1` à `L4`) de l'onduleur, dans le cas de référence un SolarEdge de 4 000 W.

- **11 niveaux** : 0 %, 10 %, …, 100 % (pas de 10 %), chaque niveau correspondant à un code binaire sur les quatre relais :

| Niveau | 100 | 90 | 80 | 70 | 60 | 50 | 40 | 30 | 20 | 10 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Code `L4 L3 L2 L1` | 0000 | 1001 | 1000 | 0111 | 0110 | 0101 | 0100 | 0011 | 0010 | 0001 | 1010 |

- La puissance nominale est réglable (`inverter_power_w`, 4 000 W par défaut). Un capteur de puissance réelle de l'onduleur est optionnel et purement informatif.
- Le réseau est le retour réel : chaque commande est suivie d'une vérification (ACK onduleur, puis mesure réseau) avant toute nouvelle correction, avec des tolérances réglables.
- En politique Compensation, ou si la réinjection est rémunératrice, l'onduleur est libéré à 100 %.
- Dans les autres cas, le moteur simule l'effet de chaque palier sur la trame courante (import et export prévus) et choisit le meilleur score. L'import est pondéré 1 et la réinjection 2 par défaut. Une marge de score évite les changements de palier inutiles.
- Le bouton `Libérer l'onduleur à 100 %` force le retour à pleine puissance.

> En cas de doute à la mise en service : coupez `Régulation FoxCat active`, appuyez sur `Libérer l'onduleur à 100 %`.

---

## 5. Machines

Les machines ne sont pas limitées à une liste fixe : elles se gèrent dans **Équipements → Machines** (ajout, modification, suppression).

Chaque machine possède un identifiant stable, un nom et un type :

- **`switch`** : commandée par une prise. Elle peut avoir un capteur de cycle (cycle protégé), un capteur de puissance, un réglage « gestion automatique » et **deux plages horaires** d'autorisation (défaut 21:30 → 07:00 et 10:30 → 17:00).
- **`cvc`** : suivie par un capteur de puissance obligatoire, **non commandée**.

Les trois machines historiques (lave-linge, sèche-linge, lave-vaisselle) sont migrées automatiquement tant qu'aucune liste personnalisée n'a été enregistrée.

Règles importantes :

- Un **cycle protégé** n'est jamais interrompu par FoxCat.
- Le mode Manuel ne commande aucune prise machine.
- Chaque machine a ses boutons `Démarrage utilisateur` et `Arrêt utilisateur`, ainsi qu'un interrupteur d'activation.
- Un bouton `Réconcilier les prises machines` remet les prises en cohérence avec les plages.
- Un enregistreur d'apprentissage mesure l'énergie consommée par cycle (visible en mode développeur).

---

## 6. Protection du raccordement (écrêtage de pointe)

Fonction **désactivée par défaut** (`Délestage haute consommation`). Elle protège le raccordement lorsque la consommation devient trop élevée (cuisson, plusieurs appareils en même temps).

**Seuil de déclenchement** : soit un seuil absolu (`high_load_trigger_w`, 5 000 W), soit un pourcentage du calibre du disjoncteur principal (90 % par défaut), avec :

```text
puissance du raccordement = calibre (A) × tension (V) × nombre de phases
```

Exemple : 40 A × 230 V × 1 phase = 9 200 W, donc déclenchement à 8 280 W.

**Mesure** : la puissance de la maison (par défaut) ou l'import réseau.
**Confirmation** : 1 trame avec disjoncteur renseigné, 2 sans. **Réarmement** : seuil plus bas (au moins 5 % sous le déclenchement) confirmé sur 5 trames.

**Actions au déclenchement** (chacune désactivable) :

- le boiler est arrêté ;
- les machines marquées délestables sont coupées (jamais pendant un cycle protégé) ;
- l'onduleur est libéré à 100 % ;
- les nouveaux démarrages de charges flexibles sont bloqués ;
- l'assistance V2H du véhicule peut être sollicitée si elle est configurée.

Le mode Manuel n'applique pas le délestage.

---

## 7. IA, prévisions solaires et batterie / VE virtuels

### Prévisions solaires et module IA (optionnel)

Onze capteurs de prévision peuvent être renseignés (maintenant, heure en cours, heure suivante, aujourd'hui, reste à produire, +1 h, +12 h, +24 h, pic aujourd'hui, demain, pic demain). Une entité **AI Task** de Home Assistant peut enrichir l'analyse. Ce module est **consultatif** : si l'IA est indisponible, FoxCat conserve son repli déterministe, et les décisions opérationnelles restent prises par le moteur. Le bouton `Analyser la prévision solaire` déclenche une analyse. L'interrupteur `Arbitrage prévision solaire` neutralise l'influence de la prévision sur l'arbitrage dynamique.

### Batterie et véhicule électrique virtuels

Simulation **en lecture seule et désactivée par défaut** : elle ne commande aucun équipement physique et n'altère pas la comptabilité réelle. Les valeurs simulées doivent toujours être distinguées des mesures. Valeurs par défaut : batterie 10 kWh / 5 kW ; véhicule 80 kWh / 7,4 kW. Détails dans [`virtual_assets/README.md`](custom_components/foxcat_energy/virtual_assets/README.md).

### V2H physique (optionnel)

Fonction distincte, **désactivée par défaut**, qui exige un interrupteur de commande, un capteur d'état de charge réel et une réserve minimale configurés explicitement.

---

## 8. Installation

### Avec HACS

1. HACS → **Intégrations** → menu **Dépôts personnalisés**.
2. Ajouter `https://github.com/Fr411/FoxCat-Energy`, catégorie **Intégration**.
3. Installer **FoxCat Energy**, puis redémarrer Home Assistant.
4. **Paramètres → Appareils et services → Ajouter une intégration → FoxCat Energy**.

### Manuelle

Copier `custom_components/foxcat_energy` dans `/config/custom_components/foxcat_energy`, redémarrer, puis ajouter l'intégration depuis l'interface.

### Avant d'activer la régulation

- Désactivez les automatisations existantes qui commandent les mêmes équipements (commandes concurrentes).
- Vérifiez les mesures, le signe du réseau et les retours RRCR dans le dashboard et le diagnostic.
- Laissez `Régulation FoxCat active` sur OFF pour le premier contrôle.

### Mise à jour

Redémarrez complètement Home Assistant après la mise à jour, puis ouvrez **Reconfigurer** et terminez avec **Enregistrer et quitter**. Les réglages sont migrés automatiquement.

---

## 9. Configuration

### À l'installation

Le flux demande successivement :

1. **Le contrat** : *Tarif HP/HC* (mono-horaire ou bi-horaire, avec leurs sources de prix) ou *Tarif Dynamique* (Simple ou Impact).
2. **Les sources énergétiques** : puissance réseau signée, convention de signe, production PV. Facultatif : protection du raccordement, source de secours, mode développeur.
3. **Le boiler** : thermostat (`climate`), température, puissance, état, sonde de résistance, et un modèle thermique (volume, puissance de la résistance, température d'eau froide) utilisé par l'arbitrage dynamique.
4. **L'onduleur** : les relais RRCR `L1` à `L4`.
5. **Les machines**, puis la **tarification dynamique** si besoin, puis l'**IA et les prévisions**.

### Dans les options (Équipements → Reconfigurer)

Menu principal : Sources de mesure · Tarification · Équipements (Onduleur, Boiler, Machines, Batterie + VE) · Protection du raccordement · IA et prévisions solaires · À propos du fonctionnement · **Enregistrer et quitter**.

**Les modifications restent en attente tant que vous n'avez pas choisi « Enregistrer et quitter » : fermer la fenêtre avant les annule.**

Tous les seuils courants (températures, tolérances, seuils PRI, seuils solaires, seuils de prix) existent aussi comme entités `number`, modifiables sans repasser par la configuration.

---

## 10. Entités, services et dashboards

### Plateformes

`sensor`, `binary_sensor`, `switch`, `select`, `number`, `time`, `button`.

### Interrupteurs principaux

`Régulation FoxCat active` · `Boiler géré par FoxCat` · `Boiler autorisé en heures creuses` · `Boiler : attendre le dernier failback en HC` · `Réduction de puissance onduleur` · `Agressivité solaire Bihoraire` · `Délestage haute consommation` · `Analyse prédictive IA` · `Optimisation économique des charges flexibles` · `Charge réseau si prix dynamique négatif` · `Résumé EMS persistant`, plus un interrupteur par machine.

### Sélecteurs

Mode, régime tarifaire, source de prix, structure tarifaire, profil de distribution, politique réseau, version de dashboard tablette/PC et mobile.

### Boutons

`Libérer l'onduleur à 100 %` · `Réinitialiser le cycle EMS` · `Réconcilier les prises machines` · `Démarrage / Arrêt utilisateur Boiler` · `Boiler retour automatique EMS` · `Lancer un diagnostic EMS` · `Analyser la prévision solaire` · `Régénérer le dashboard FoxCat` · `Enregistrer mon dashboard personnalisé` · `Appliquer mes personnalisations à la dernière version`. En mode développeur : deux boutons de simulation de prix (négatif, HP très élevé), sans effet sur les prix réels.

### Services

| Service | Rôle |
|---|---|
| `foxcat_energy.save_settings_profile` | Enregistre les réglages dans `/config/foxcat_energy/profiles/<nom>.json`. |
| `foxcat_energy.load_settings_profile` | Valide puis applique un profil. |
| `foxcat_energy.reset_settings` | Remet les valeurs par défaut du moteur et des machines. |

### Dashboards

FoxCat génère deux dashboards YAML dans `/config/foxcat_energy/` : `dashboard.yaml` (tablette / PC) et `dashboardmob1.yaml` (mobile). Un dashboard existant n'est **jamais** écrasé au démarrage ; le bouton de régénération crée d'abord une sauvegarde `.bak`. Les personnalisations peuvent être enregistrées puis réappliquées sur une version plus récente.

Pour que Home Assistant les affiche, fusionnez **une seule fois** [`configuration.yaml.snippet`](configuration.yaml.snippet) dans `configuration.yaml`, puis redémarrez. Détails : [`README-INSTALL.md`](README-INSTALL.md) et [`PREMIUM_UI_INSTALL.md`](PREMIUM_UI_INSTALL.md) (la vue Premium utilise `custom:button-card`).

---

## 11. Valeurs par défaut

| Catégorie | Valeur |
|---|---|
| Régulation | OFF |
| Mode | Éco |
| Politique réseau | Compensation |
| Source de prix / structure | Variable via entités HA / Simple |
| Boiler | 1800 W · reprise 43 °C · confort 45 °C · boost 65 °C · sécurité 68 °C · cycle min 120 s |
| Failback HC | attendre = ON · marge 30 min |
| Dynamique | favorable 30 % · plafond 70 % |
| PRI | pas de 10 % (≈ 400 W) · onduleur 4 000 W · pondération import 1 / réinjection 2 |
| Stabilité T0/T1 | 500 W |
| Délestage | OFF · seuil 5 000 W · réarmement 3 500 W · 90 % du disjoncteur |
| Batterie / VE virtuels | OFF |
| Mode développeur | OFF |

---

## 12. Limites et points à connaître

- **Éco et Confort sont identiques côté boiler.** Les deux appellent la même fonction de décision ; la différence entre « économiser » et « privilégier le confort » n'est pas encore implémentée dans le moteur actif.
- **La sécurité thermique n'est pas un thermostat de sécurité.** Elle dépend de la sonde configurée. Gardez le thermostat mécanique de votre chauffe-eau.
- **Validation terrain.** Les tests logiciels et simulations ne remplacent pas une validation sur l'installation réelle ; le dépôt est en développement actif.
- **Un seul chauffe-eau** est géré (une entité `climate`).
- **Une seule installation** FoxCat par Home Assistant.
- **Dashboards en YAML** : une configuration unique dans `configuration.yaml` est nécessaire.

---

## 13. Développement et tests

### Organisation du code

```text
custom_components/foxcat_energy/
├── __init__.py            # setup, services de profils, dashboards
├── config_flow.py         # installation et options
├── const.py               # constantes, réglages par défaut, entités
├── runtime/               # coordinateur, cœur onduleur, bus d'énergie, migrations, profils
├── domain/
│   ├── engine/            # décisions boiler (modes/), PRI, garde de charge
│   ├── tariff/            # périodes HP/HC, Impact, modèle tarifaire
│   ├── pricing/           # analyseur de prix, optimiseur économique, planificateur Day-Ahead
│   ├── loads/             # machines, cycles, apprentissage, planificateur de charges flexibles
│   └── accounting/        # comptabilité mono-horaire, bi-horaire, dynamique
├── trading/               # VPP, batterie et VE virtuels
├── dashboard/             # génération, versions et fusion des dashboards
├── peak_shaving.py        # écrêtage de pointe (logique pure)
└── grid_load.py           # calcul de charge du raccordement
```

### Lancer les tests

```bash
python3 -m unittest discover -s tests
```

La suite n'a pas besoin de Home Assistant : 151 tests, dont 30 ignorés faute de dépendances.

### Documentation du dépôt

- [`CHANGELOG.md`](CHANGELOG.md) : journal détaillé des changements.
- [`JOURNAL_VERSIONS.md`](JOURNAL_VERSIONS.md) : jalons de versions.
- [`docs/archive/`](docs/archive/) : audits, notes de migration, anciens README et anciennes versions de dashboards.

Licence : voir [`Licence.md.txt`](Licence.md.txt).
