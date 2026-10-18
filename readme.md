# FoxCat Energy ⚡️🐱

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/Release-1.5.0-green.svg)](#historique-des-versions)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey.svg)](LICENSE)

**FoxCat Energy** est un système de gestion d'énergie domestique (EMS — *Energy Management System*) déterministe, temps réel et orienté événement pour **Home Assistant**.

Il optimise l'autoconsommation photovoltaïque, pilote le bridage d'injection dynamique (PRI / contact RRCR SolarEdge), protège le disjoncteur général via un délestage intelligent, optimise la charge d'eau chaude sanitaire (ECS) et arbitre les charges en fonction des régimes tarifaires (fixe, HP/HC ou dynamique horaire).

---

## 📖 Sommaire

1. [Présentation](#-présentation)
2. [Principes de Conception](#-principes-de-conception)
3. [Fonctionnement & Architecture](#-fonctionnement--architecture)
   - [Bus d'Énergie & Cadencement](#bus-dénergie--cadencement)
   - [Gestionnaire d'Onduleur & Régulateur PRI](#gestionnaire-donduleur--régulateur-pri)
   - [Arbitre Thermique & Surplus Virtuel](#arbitre-thermique--surplus-virtuel)
   - [Protection des Charges & Délestage](#protection-des-charges--délestage)
   - [Comptabilité & Régimes Tarifaires](#comptabilité--régimes-tarifaires)
4. [Modes de Fonctionnement](#-modes-de-fonctionnement)
5. [Installation & Configuration](#-installation--configuration)
6. [Historique des Versions](#-historique-des-versions)

---

## 🌟 Présentation

Face aux contraintes des réseaux électriques modernes (zéro injection imposé, tarifs négatifs dynamiques, pics de capacité quart-horaires), les automatisations Home Assistant classiques montrent vite leurs limites : instabilités en boucle fermée, courses critiques (*race conditions*) et oscillations de relais.

**FoxCat Energy** répond à ces enjeux en introduisant un moteur de régulation industriel au sein d'une intégration Home Assistant :
* **Déterministe :** chaque décision repose sur un échantillonnage horodaté et validé physiquement.
* **Résilient :** tolérant aux coupures temporaires de télémétrie (ex. reboot périodique de passerelle de mesure Smappee).
* **Respectueux du matériel :** réduction drastique de l'usure des relais et actionneurs par quantification discrète et filtres anti-pompage.

---

## 🧠 Principes de Conception

FoxCat Energy repose sur 5 piliers fondamentaux :

1. **Horloge souveraine de trame :**  
   Le cycle décisionnel principal est cadencé sur la trame de puissance active de la maison (typiquement issue du capteur Smappee/compteur réseau toutes les ~30 s). Aucune boucle concurrente non contrôlée ne peut altérer la décision.
2. **Validation $N+1$ (Boucle fermée réelle) :**  
   Toute action physique (variation de palier de bridage, enclenchement du chauffe-eau) n'est validée qu'à la trame suivante ($N+1$). Aucun ordre successif n'est envoyé sans avoir mesuré l'impact de l'ordre précédent.
3. **Surplus solaire reconstitué (Surplus virtuel) :**  
   Pour éviter le phénomène de clignotement (allumage d'une charge $\rightarrow$ disparition du surplus $\rightarrow$ extinction), FoxCat réintègre la puissance mesurée du chauffe-eau dans le calcul de la balance réseau :
   $$\text{Surplus}_{\text{virtuel}} = \text{Puissance}_{\text{export}} + \text{Puissance}_{\text{boiler}}$$
4. **Sanctification des cycles machines :**  
   Un cycle commencé (lave-linge, lave-vaisselle, sèche-linge) est prioritaire et protégé. Il ne peut jamais être interrompu par une fin de plage horaire ou un délestage d'urgence.
5. **Découplage physique / économique :**  
   La couche de régulation énergétique assure la sécurité physique de l'habitat indépendamment des calculs financiers (module comptable dédié).

---

## ⚙️ Fonctionnement & Architecture

La version **1.5.0** introduit un découplage modulaire complet :

```
       [Capteurs Réseau / Smappee]
                   │
                   ▼
         ┌───────────────────┐
         │   EnergyBus       │ ◄── Événements urgents & télémétrie
         └─────────┬─────────┘
                   │ Trame synchrone
                   ▼
         ┌───────────────────┐
         │     EMS CORE      │
         ├───────────────────┤
         │ • Load Guard      │ ──► Délestage & Cycles protégés
         │ • Inverter Core   │ ──► Régulateur PI discret & RRCR
         │ • Boiler Arbiter  │ ──► Sécurité thermique 65/68 °C
         │ • Strategy Modes  │ ──► Eco, ECS, Zéro Inj, Dynamic, Manuel
         └─────────┬─────────┘
                   │
                   ▼
         ┌───────────────────┐
         │    Accounting     │ ──► Calculs financiers, HP/HC, Solde net
         └───────────────────┘
```

### Bus d'Énergie & Cadencement (`energy_bus.py`)
Le bus centralise et distribue la télémétrie énergétique :
* Filtrage des états aberrants, gel de l'intégrale lors d'un état `unavailable`/`unknown`.
* Trame de stabilisation obligatoire après reconnexion d'un compteur avant reprise des décisions.
* Transmission prioritaire des alertes de surconsommation instantanée.

### Gestionnaire d'Onduleur & Régulateur PRI (`inverter_core.py`, `pri.py`)
Pilote le bridage SolarEdge via contact sec (relais RRCR 0–100 % par pas de 10 %) :
* **Régulateur PI discret** avec anti-windup.
* Consigne réseau par défaut légèrement exportatrice (+75 W) pour garantir le zéro injection sans pompage.
* Comparateur de cohérence PV : empêche de conclure faussement à une fin de production lorsque les panneaux sont intentionnellement bridés.

### Arbitre Thermique & Surplus Virtuel (`modes/ecs_solar.py`, `modes/eco.py`)
* Gestion du boiler résistif avec gardes de sécurité thermique (65 °C opérationnel, coupure haute d'urgence à 68 °C).
* Autorisation conditionnelle du boiler pendant un cycle machine protégé si le surplus virtuel net couvre la puissance nominale.

### Protection des Charges & Délestage (`load_guard.py`)
* Détection de surconsommation basée sur la puissance totale de la maison.
* Déclenchement sur hystérésis temporelle (ex. 2 trames hautes consécutives pour délester, 5 trames basses consécutives pour réarmer).
* En délestage : libération immédiate du PRI à 100 %, coupure boiler et coupure des appareils non protégés. Les cycles protégés actifs ne sont pas coupés.

### Comptabilité & Régimes Tarifaires (`accounting/`, `tariff.py`)
* Prise en charge des régimes : **Compensation**, **Bi-horaire (HP/HC)** et **Dynamique horaire (ex. Nord Pool, EPEX Spot)**.
* Entités de coût instantané, valeur d'injection et solde économique net.
* Détection des prix négatifs pour chargement réseau forcé du boiler jusqu'à 65 °C.

---

## 🎛 Modes de Fonctionnement

| Mode | Description |
[CONFIGURATION DU CONTRAT ET DU RÉSEAU WALLON]
  │
  ├── 1. RÉGIME TARIFAIRE / CONTRAT ÉNERGIE (select.foxcat_energy_tarification_regime_tarifaire)
  │     │
  │     ├── A. Mono-horaire / Fixe
  │     │     └── Valorisation : Tarif unique global (pas de distinction horaire)[cite: 6].
  │     │
  │     ├── B. Bi-horaire (HP / HC)
  │     │     ├── Paramètres : Saisie des prix HP/HC ou liaison via entités (ex: Luminus ComfyFlex)[cite: 6, 9, 11]
  │     │     └── Plages : Piloté par les entités temporelles (HP / HC)[cite: 2, 8]
  │     │
  │     └── C. Dynamique (Day-Ahead / DED)
  │           ├── Sources : Indexation heure par heure (ex: Luminus Dynamic / ENTSO-E)[cite: 1, 6, 11]
  │           └── Sous-structures & Variantes de Tarifs Dynamiques :
  │                 ├── 1. Standard Day-Ahead (Luminus Dynamic, Engie Direct, etc.)
  │                 │     ├── Prix d'achat horaire (all_in) + Prix de réinjection dédié
  │                 │     ├── Seuil favorable réglable (défaut 30 %) pour déclencher le stockage/charges[cite: 10, 13]
  │                 │     └── Plafond acceptable / Zone de pic (défaut 70 %) pour bloquer les prélèvements non urgents[cite: 10, 13]
  │                 ├── 2. Tarifs Dynamiques avec Option Prix Négatifs
  │                 │     └── Switch actif : Forçage de charge réseau (ex: Boiler jusqu'à 65 °C) lorsque le marché est négatif[cite: 6, 25]
  │                 └── 3. Tarifs Dynamiques couplés au Profil Réseau Wallon
  │                       └── Croisement avec la structure de distribution locale
  │
  ├── 2. PROFIL DE DISTRIBUTION & COMPTAGE (Wallonie) (select.foxcat_energy_tarification_profil_distribution_belgique)
  │     ├── A. Simple (un tarif, toutes les heures)[cite: 2, 4]
  │     ├── B. Bi-horaire (jour / nuit)[cite: 2, 4]
  │     └── C. Tarif Impact (3 plages horaires CWApe)[cite: 2, 4]
  │           ├── Période PIC : 17h – 22h (Alerte / Évitement des pointes réseau)[cite: 2, 4]
  │           ├── Période MEDIUM : 7h – 11h + 22h – 1h[cite: 2, 4]
  │           └── Période ECO : 1h – 7h + 11h – 17h (Favorable aux reports)[cite: 2, 4]
  │
  └── 3. POLITIQUE RÉSA / RÉINJECTION (select.foxcat_energy_tarification_politique_reseau)
        ├── A. Régime de compensation (Wallonie, certifié pré-2024, onduleur libéré à 100 % jusqu'en 2030)[cite: 3]
        ├── B. Tarif d'injection (Compteur communicant / Post-2024)[cite: 3]
        │     └── Convention signée : Valeur positive = revenu (revente) / Valeur négative = coût de réinjection[cite: 7, 10]
        └── C. Zéro injection (Best effort / strict)[cite: 5, 11]

---

## 📦 Installation & Configuration

### Via HACS (Recommandé)
1. Ouvrez HACS dans Home Assistant $\rightarrow$ **Intégrations** $\rightarrow$ Menu trois points en haut à droite $\rightarrow$ **Dépôts personnalisés**.
2. Ajoutez l'URL de ce dépôt avec la catégorie **Intégration**.
3. Cliquez sur **Télécharger**, puis redémarrez Home Assistant.

### Configuration
1. Rendez-vous dans **Paramètres** $\rightarrow$ **Appareils et services** $\rightarrow$ **Ajouter une intégration**.
2. Recherchez **FoxCat Energy**.
3. Associez vos entités clés :
   - Capteur de puissance maison (horloge souveraine)
   - Capteurs réseau (import / export)
   - Capteur de production photovoltaïque
   - Prises/relais commandés (Boiler, machines)
   - Capteur de température d'eau
4. Ajustez les seuils dans le menu **Reconfigurer** à tout moment sans redémarrage.

---

## 📜 Historique des Versions

### 1.5.0
* **Architecture :** Introduction du bus d'événements centralisé `energy_bus.py`.
* **Abstraction matérielle :** Création d'`inverter_core.py` isolant le contrôle bas-niveau onduleur/RRCR.
* **Résilience :** Découplage strict entre la boucle de régulation critique et le coordinator Home Assistant.
* **Tarification :** Consolidation du gestionnaire financier et fiabilisation des commutations de régime tarifaire à chaud.

### 1.4.0 — 1.4.8
* Structuration complète du module comptable `accounting/manager.py`.
* Intégration de la plateforme `diagnostics` et des boutons d'actions manuelles sécurisées.
* Support complet de la distribution HACS (`branding/`, traductions FR).

### 1.3.200 — 1.3.203
* Horloge souveraine cadencée sur la trame de consommation réelle de la maison.
* Régulateur PI discret anti-windup pour le zéro injection avec consigne export (+75 W).
* Résilience aux resets périodiques Smappee (gel de l'intégrale et trame de stabilisation).
* Algorithme de surplus virtuel avec réintégration de la puissance boiler.

### 1.1.0 — 1.3.1
* Gestion extensible des machines ON/OFF et cycles protégés.
* Détecteur de haute consommation avec délestage intelligent à hystérésis.
* Support initial des tarifs dynamiques et charge sur prix négatifs.

---

## 📄 Licence

Distribué sous licence **Apache 2.0**. Consultez le fichier `LICENSE` pour plus de détails.
