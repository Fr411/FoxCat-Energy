# FoxCat Energy

**FoxCat Energy** est une intégration Home Assistant de gestion énergétique résidentielle (EMS, *Energy Management System*). Elle observe la maison en continu, valorise localement l'énergie solaire, pilote le chauffe-eau, les machines et l'onduleur, protège le raccordement, et chiffre en euros ce que coûte et ce que rapporte chaque kWh.

| | |
|---|---|
| Version de l'intégration | **1.7.6** |
| Home Assistant minimal | **2025.1.0** |
| Domaine | `foxcat_energy` |
| Langue de configuration | Français |

Pour installer et configurer pas à pas, lisez le **[Manuel](MANUEL.md)**. Ce document-ci explique **comment FoxCat fonctionne**. Les changements de chaque version sont dans le [journal des versions](CHANGELOG.md).

---

## Sommaire

1. [Idée générale](#1-idée-générale)
2. [Architecture](#2-architecture)
3. [Mesures et sources](#3-mesures-et-sources)
4. [Les trois réglages indépendants](#4-les-trois-réglages-indépendants)
5. [Tarification](#5-tarification)
6. [Comparateur de tarifs et coûts réseau](#6-comparateur-de-tarifs-et-coûts-réseau)
7. [Comptabilité énergétique et financière](#7-comptabilité-énergétique-et-financière)
8. [Boiler (chauffe-eau)](#8-boiler-chauffe-eau)
9. [Onduleur et PRI / RRCR](#9-onduleur-et-pri--rrcr)
10. [Machines](#10-machines)
11. [Chauffage : décalage de consigne](#11-chauffage--décalage-de-consigne)
12. [Protection du raccordement](#12-protection-du-raccordement)
13. [Batterie et véhicule électrique](#13-batterie-et-véhicule-électrique)
14. [Prévisions, IA et planification](#14-prévisions-ia-et-planification)
15. [Entités, appareils et services](#15-entités-appareils-et-services)
16. [Dashboards et cartes](#16-dashboards-et-cartes)
17. [Sécurité et limites](#17-sécurité-et-limites)
18. [Dépôt, tests et licence](#18-dépôt-tests-et-licence)

---

## 1. Idée générale

FoxCat n'est ni un simple tableau de bord ni une automatisation unique : c'est un **moteur de décision** qui mesure, vérifie ses données, applique des sécurités, décide, commande, puis contrôle que l'effet attendu s'est produit.

La logique d'arbitrage est toujours la même :

```text
Produire utilement
      ↓
Consommer localement
      ↓
Déplacer les usages flexibles vers le soleil ou les prix bas
      ↓
Limiter la production en dernier recours
      ↓
Éviter une réinjection sans valeur (ou payante)
```

Principes :

- **Le moteur temps réel reste souverain.** Les modules prédictifs (prévisions, IA, Day-Ahead) conseillent, mais ne commandent jamais directement un équipement.
- **Les usages utiles passent avant le bridage.** Avant de réduire la production photovoltaïque, FoxCat cherche à utiliser le surplus : eau chaude, machines, chauffage. L'onduleur est la dernière couche d'ajustement.
- **Une décision n'est « exécutée » qu'une fois confirmée.** FoxCat attend un accusé de commande, puis un accusé physique (la puissance mesurée a bien changé).
- **Les sécurités sont prioritaires** sur toute optimisation (température de résistance du boiler, disjoncteur, cycles de machines).
- **Tout est local.** L'apprentissage est passif et stocké dans Home Assistant.

## 2. Architecture

```text
CAPTEURS ──► VALIDATION ──► CONTEXTE TARIFAIRE ──► MODE EMS ──► ARBITRE
                                                                 ├─ Boiler
                                                                 ├─ Machines
                                                                 ├─ Chauffage (décalage)
                                                                 ├─ Batterie / V2H
                                                                 └─ Onduleur (PRI)
                                                                       │
                              EXÉCUTION ──► ACK commande ──► ACK physique ──► ACK énergétique
```

| Brique | Rôle |
|---|---|
| **EMS Core** | Décideur souverain. Ses réglages sont exposés comme entités (interrupteurs, nombres, listes). |
| **Energy Bus** | Bus interne entre modules : trames, commandes, événements, accusés (ACK / NOK). |
| **Métronome** | Surveille la fraîcheur de la mesure réseau et bascule sur la source de secours si elle se fige. Ce n'est pas une horloge périodique. |
| **Moteur tarifaire** | Calcule le prix d'achat actif, la valeur de la réinjection, la période (HP/HC…) et le statut du prix. |
| **Comptabilité** | Convertit chaque trame en kWh et en euros (jour, mois, année). |
| **Comparateur** | Rejoue chaque tarif sur la consommation mesurée. |
| **Machine Learning** | Apprend passivement les cycles des machines, sans influencer les décisions. |
| **Diagnostic** | Capteurs techniques, mode développeur, scénarios de simulation sans effet sur le réel. |

## 3. Mesures et sources

Deux mesures physiques suffisent, et elles sont obligatoires :

1. **la puissance réseau signée** au point de raccordement (cadence l'EMS) ;
2. **la production photovoltaïque** instantanée.

À partir d'elles, FoxCat **calcule lui-même** la consommation de la maison, le prélèvement, la réinjection, l'autoconsommation, le taux d'autonomie et les bilans : aucun capteur supplémentaire n'est nécessaire.

La **convention de signe** est réglable (+ prélèvement / − réinjection, ou l'inverse) pour s'adapter à votre compteur. Une source de secours facultative est utilisée uniquement si la source principale perd sa fraîcheur.

## 4. Les trois réglages indépendants

Trois choix distincts, qu'il ne faut pas confondre :

| Réglage | Valeurs | Ce qu'il décide |
|---|---|---|
| **Mode EMS** | Éco · Confort · Manuel | Le comportement des charges pilotées |
| **Régime tarifaire** | Mono-horaire · Bi-horaire (HP/HC) · Dynamique | Comment le prix d'achat est déterminé |
| **Politique réseau** | Compensation · Injection tarifée · Injection non valorisée · Zéro injection | Ce que vaut (ou coûte) la réinjection, et donc l'attitude face au surplus |

### Modes EMS

- **Éco** : priorité à l'autoconsommation et à l'optimisation automatique. Le boiler absorbe d'abord le surplus solaire réellement disponible ; l'onduleur traite l'excédent résiduel ; aucun achat en heures pleines n'est autorisé pour le boiler. Les anciens modes (Zéro injection, ECS solaire, Bihoraire, Dynamique, Maxi solaire…) sont migrés vers Éco : leur comportement est désormais porté par le régime tarifaire et la politique réseau.
- **Confort** : privilégie le confort tout en conservant toutes les sécurités.
- **Manuel** : suspend les actions automatiques sur le boiler, l'onduleur et les machines. La sécurité thermique du boiler reste active.

### Politique réseau

- **Compensation** : la réinjection compense le prélèvement ; le surplus est valorisé au prix d'achat.
- **Injection tarifée** : la réinjection est vendue au prix de réinjection (fixe ou dynamique) ; FoxCat tolère une injection maximale et un import cible (réglables).
- **Injection non valorisée** : la réinjection ne rapporte rien ; FoxCat cherche à l'éviter.
- **Zéro injection** : FoxCat vise une injection nulle en utilisant le surplus puis en bridant l'onduleur.

> Le mode EMS, le régime et la politique ne se verrouillent pas entre eux : vous pouvez les combiner librement.

## 5. Tarification

### Deux axes indépendants : contrat × réseau

- Le **contrat** (source des prix) : prix saisis à la main, lus depuis des capteurs Home Assistant, ou **dynamique** (prix horaire ou au quart d'heure, Day-Ahead).
- La **structure du réseau** : **mono-horaire** (un prix), **bi-horaire** (heures pleines / creuses) ou **Impact** (périodes ECO / MEDIUM / PIC).

Toutes les combinaisons existent, par exemple Impact avec un contrat fixe, ou bi-horaire avec un contrat dynamique. L'écran **Contrat et réseau** écrit ensemble la source, la structure, le régime et le profil de distribution pour qu'ils restent cohérents.

### Prix tout compris

Case **« Mes prix sont tout compris »** (décochée par défaut) : si le prix lu contient déjà réseau, taxes et marge, FoxCat n'y ajoute plus de complément de distribution, ce qui évite un double comptage.

### Prix fixe, variable, intégration externe

- **Prix saisis** : vous encodez le prix d'achat (ou HP et HC) et, en option, le prix de réinjection.
- **Capteurs** : FoxCat lit vos capteurs de prix. Aucune entité d'un fournisseur précis n'est préremplie.
- **Intégration externe** : par exemple Luminus Dynamic, Nord Pool, ENTSO-E ou `be_electricity_prices`. Les prix de gros (Nord Pool, ENTSO-E) servent d'**indicateurs de temps** (publication du lendemain), jamais de prix payé.

### Dynamique Day-Ahead

FoxCat lit la courbe « tout compris » d'aujourd'hui et de demain, ainsi que la valeur de réinjection. Il positionne le prix actuel sur l'horizon de 24 h (position en %, rang, tendance), repère le **prochain creux** et le **prochain pic**, le meilleur créneau futur et l'économie possible en reportant un usage. Le planificateur Day-Ahead est **strictement dynamique** et informatif ; le planificateur de charges flexibles reste le seul décideur du feu vert de démarrage.

Réglages utiles : horizon, seuil de position « favorable » (30 % par défaut), seuil de pic, durée favorable maximale (4 h), charge réseau quand le prix devient négatif.

### Publication des prix

Une entité (par exemple « prix de demain disponible ») déclenche la relecture des prix, avec un service optionnel (par exemple `be_electricity_prices.refresh`), appelé au plus **une fois toutes les 10 minutes**.

### Ce que FoxCat expose

Prix d'achat actif et suivant, valeur économique de la réinjection, période, statut du prix (avantageux / normal / élevé), prix négatif actif, position et rang sur la courbe, tendance, meilleur prix et créneau futurs, coût et valeur instantanés (€/h), solde réseau instantané.

## 6. Comparateur de tarifs et coûts réseau

**Comparateur.** FoxCat enregistre la consommation et les prix au quart d'heure (stockage séparé, 62 jours) et **rejoue chaque tarif configuré** sur cette consommation réelle. Deux capteurs, « Comparateur de tarifs • Aujourd'hui » et « • Ce mois », donnent le tarif le moins cher, le coût net de chaque tarif et l'écart avec le tarif actuel (négatif = moins cher). Les tarifs « actuel » et « contrat saisi » sont ajoutés automatiquement.

- Modèles belges prédéfinis : Wallonie mono, bi-horaire 2026, Impact. Chargement automatique selon la région.
- Tarifs personnalisés en JSON, copiables d'une installation à l'autre.
- **Comparaison à comportement constant** : le pilotage de FoxCat n'est pas rejoué. Un tarif dynamique serait en réalité encore meilleur si FoxCat déplaçait vos charges.
- Les créneaux sans prix connu sont signalés au lieu d'être inventés.

**Coûts réseau et prosumer.** Ils dépendent de votre gestionnaire de réseau, pas de votre fournisseur : le comparateur les applique **de la même façon à tous les tarifs**, si bien que l'écart ne reflète que le prix de l'énergie.

- *Terme capacitaire* : forfait annuel (Bruxelles) ou pointe mensuelle au quart d'heure (Flandre, avec minimum facturé).
- *Redevance prosumer* annuelle.
- Les entités de contrôle de l'intégration de prix (coût capacitaire, pointe mensuelle, coût prosumer) sont facultatives : elles servent de vérification et ne s'additionnent jamais.
- Capteur « Coûts réseau • Ce mois » : total, détail et écart de pointe entre FoxCat et l'intégration.

## 7. Comptabilité énergétique et financière

FoxCat produit, **par jour, par mois et par année** :

- énergie : consommation maison, production, autoconsommation, prélèvement, réinjection, taux d'autoconsommation et d'autonomie ;
- ventilation par tarif (dynamique, HP, HC) sans compensation énergétique ;
- finances : coût réseau brut, revenu et coût de réinjection, **coût net**, gain solaire estimé ;
- **comptabilité par appareil** (boiler, chaque machine) : énergie, part solaire, part réseau, coût, répartition HP/HC ;
- **« Économiser avec FoxCat Energy »** : ce que le pilotage a fait économiser, par jour, mois et année.

## 8. Boiler (chauffe-eau)

FoxCat commande un thermostat (entité `climate`) et confirme l'état par la puissance mesurée. États : **chauffe normale (45 °C)**, **boost solaire (65 °C)**, arrêt, ou aucune action.

Seuils par défaut (réglables) :

| Réglage | Défaut |
|---|---|
| Reprise de chauffe | 43 °C |
| Confort | 45 °C |
| Boost solaire | 65 °C |
| Sécurité résistance | **68 °C** (souveraine) |
| Cycle minimum | 120 s |
| Puissance nominale | 1 800 W |

Comportement :

- **Sécurité d'abord** : au-delà du seuil de sécurité (sonde sur la résistance), toute chauffe est interdite et un arrêt est demandé.
- **Éco** : le surplus solaire alimente le boiler jusqu'à 65 °C ; pas d'achat en heures pleines ; le boost solaire s'interrompt si le surplus disparaît.
- **Heures creuses** : FoxCat attend le **dernier failback** avant de chauffer sur le réseau, pour laisser la priorité au solaire (interrupteur actif par défaut, marge de 30 min).
- **Bihoraire** : agressivité solaire réglable.
- **Dynamique** : arbitrage thermique selon le prix. Un modèle (volume, puissance, eau froide à 15 °C) estime la durée de chauffe et réserve les créneaux les moins chers.
- **Délestage** : le boiler peut être coupé pendant une pointe de consommation.

## 9. Onduleur et PRI / RRCR

Le **PRI** réduit la puissance de l'onduleur par quatre relais **RRCR** (L1 à L4, un code de niveau). FoxCat s'en sert quand le surplus n'a plus d'usage utile ou que la réinjection est indésirable.

- Algorithme à pas (100 à 1 000 W) avec scoring import/réinjection, tolérances et fenêtres « optimal / acceptable ».
- Contrôle par **accusé physique** : la puissance de l'onduleur ou du réseau doit bouger comme prévu.
- Un capteur de **puissance live** de l'onduleur est facultatif et purement informatif.
- Niveau manuel disponible en mode Manuel ; « Libérer l'onduleur à 100 % » est le retour arrière immédiat.
- Coupé automatiquement en fin de journée solaire (seuil et confirmation réglables).

## 10. Machines

- **Lave-linge, sèche-linge, lave-vaisselle** (historiques) et **machines extensibles** : chaque machine est un switch pilotable ou un **CVC en télémétrie seule** (observé, comptabilisé séparément).
- **Fenêtre machines** : plage horaire pendant laquelle l'alimentation est autorisée.
- **Détection et protection de cycle** : une machine en cycle n'est jamais coupée en plein programme.
- **Apprentissage passif** : jusqu'à 30 cycles récents par machine mesurée.
- **Planificateur de charges flexibles** : décide du démarrage selon le surplus solaire et les prix. Il reste seul décideur de l'autorisation de démarrer.
- **Phase du réseau** par machine (L1, L2, L3) pour le calcul de charge.
- Une machine peut être marquée **délestable**.

## 11. Chauffage : décalage de consigne

Fonction **désactivée par défaut**. FoxCat calcule un décalage en °C (0 à 2 °C par pas de 0,5 °C par défaut) selon le surplus solaire et la présence, et le publie dans le capteur « Chauffage • Décalage de consigne », avec un capteur « Statut » qui donne la raison. **Une automatisation Home Assistant** applique ce décalage aux presets de **Versatile Thermostat** : FoxCat n'écrit jamais dans les `climate.*` ni dans les `number.*`.

Règles : anti-yoyo (300 s avant toute augmentation), un pas accordé est conservé tant que le surplus reste à 60 % du seuil, baisse immédiate si l'import dépasse 300 W, garde sur la puissance du groupe de climatisation. Option « uniquement maison vide ». Tout est créé par FoxCat, sans helper à créer à la main. Exemple d'automatisation : [`docs/automations/etage_decalage_vtherm.yaml`](docs/automations/etage_decalage_vtherm.yaml).

Le menu permet aussi de déclarer des **systèmes de chauffage** (pompes à chaleur : groupe extérieur, et jusqu'à 5 unités intérieures pour une PAC air/air).

## 12. Protection du raccordement

Quand la puissance dépasse un seuil, FoxCat **délestera** les charges non essentielles puis les rétablit après un retour sous le seuil de réarmement.

- Seuil : % du calibre du disjoncteur (90 % par défaut) ou seuil absolu en watts.
- Réseau mono, tri ou tétra. Si vous avez des intensités par phase, FoxCat prend la plus élevée.
- Mesure comparée : import réseau (évite de délester quand le solaire couvre la charge) ou consommation totale.
- Confirmation sur plusieurs trames avant déclenchement, **réarmement toujours au moins 5 % sous le déclenchement** pour éviter les oscillations.
- Actions : couper le boiler, couper les machines délestables (jamais en plein cycle), libérer l'onduleur à 100 %, bloquer les nouveaux démarrages flexibles, assistance V2H.

### Sans capteur d'intensité par phase

Un disjoncteur déclenche sur la phase la plus chargée, pas sur le total. Sans courant par phase, FoxCat ne peut pas savoir quelle phase est en tête. Il travaille donc avec ce qu'il a :

- **Tensions mesurées** (facultatives) : phase-neutre L1, L2, L3 (≈ 230 V) et entre lignes L1-L2, L2-L3, L3-L1 (≈ 400 V). FoxCat recoupe les deux familles, ignore les valeurs aberrantes et retombe sur la tension nominale sans mesure. La tension obtenue sert à calculer la capacité du disjoncteur et l'intensité. L'ancien capteur de tension unique reste pris en compte s'il est le seul renseigné.
- **Coefficient de déséquilibre des phases** (1 par défaut, 3 au maximum) : il suppose que la phase la plus chargée porte K fois la charge moyenne. La capacité vue du total devient `A × V × phases ÷ K`. Exemple : 25 A, 3 phases, 230 V, K = 1,3 → capacité 13 269 W, déclenchement à 90 % ≈ 11 942 W, au lieu de 15 525 W avec K = 1. Il ne s'applique ni en monophasé ni quand des intensités par phase sont mesurées.
- **Diagnostic** : les attributs de l'entité « Charge du disjoncteur principal » exposent l'intensité estimée et sa source, le coefficient appliqué, la tension utilisée et son origine (`nominal`, `phase`, `line` ou `phase+line`), la tension entre lignes et l'écart entre phases.

Les tensions améliorent la précision du calcul ; elles **ne détectent pas** une phase surchargée. Seul le coefficient en tient compte.

## 13. Batterie et véhicule électrique

- **Simulateur** de batterie domestique et de véhicule virtuels : désactivé par défaut, **sans commande physique**, isolé du registre réel. Il sert à estimer ce qu'apporterait un équipement avant de l'acheter. Les valeurs simulées sont distinguées des mesures réelles.
- **Arbitrage virtuel** à l'achat et à la revente tenant compte de l'écart de prix et du coût d'usure.
- **V2H physique** : fonction distincte, *opt-in*, avec commande configurée explicitement, réserve de mobilité obligatoire et interverrouillage avec le chauffe-eau de confort.

## 14. Prévisions, IA et planification

- **Prévisions solaires** (Forecast.Solar et capteurs de prévision) et **agent IA Home Assistant** (AI Task) facultatif. Le module est consultatif ; sans IA, FoxCat garde un repli déterministe.
- **Price Analyzer V2** : statistiques du jour et de demain, position et rang, fraîcheur et continuité des données, série complète exposée en attribut pour les graphiques.
- **Planificateur de charges flexibles** (V1.7.1) : seul décideur de l'autorisation de démarrer.
- **Optimiseur économique** et arbitrage de prévision solaire, activables séparément.

## 15. Entités, appareils et services

Les entités sont rangées en **10 appareils** : Mesures et sources · Tarification · Onduleur · Boiler · Chauffage · Machines · Batterie et VE · Protection · Prévisions et IA · Système. Les `entity_id` et `unique_id` sont stables : dashboards et automatisations existants continuent de fonctionner.

Principaux interrupteurs : Régulation FoxCat active, Boiler géré par FoxCat, Boiler autorisé en heures creuses, Réduction de puissance onduleur, Gestion de chaque machine, Délestage haute consommation, Analyse prédictive IA, Optimisation économique, Prédictif prix dynamique, Décalage de consigne solaire, Résumé EMS persistant.

Listes : Mode EMS, Politique réseau, Version du dashboard, et cinq listes de tarif : **Source du prix**, **Structure tarifaire**, **Régime Tarifaire**, **Profil distribution Belgique** et **Structure (Si Dynamique)**.

Ces cinq listes sont **synchronisées avec l'écran « Contrat et réseau »** : elles ne modifient que deux choix, le contrat et la structure du réseau, et FoxCat en déduit toutes les autres clés (régime, famille, profil de distribution, structure dynamique). Changer une liste met donc à jour les autres, et le menu affiche la même chose.

| Liste | Choix | Ce qu'elle change |
|---|---|---|
| Source du prix | Contractuelle / fixe · Variable via entités Home Assistant · Dynamique Day-Ahead (· Intégration externe si déjà active) | Le contrat |
| Structure tarifaire | Simple · Bi-horaire · Impact | La structure du réseau, avec tous les contrats |
| Régime Tarifaire | Mono-horaire · Bi-horaire (HP/HC) · Dynamique | Dynamique = contrat dynamique ; Mono ou Bi = contrat non dynamique et structure simple ou bi-horaire |
| Profil distribution Belgique, Structure (Si Dynamique) | Simple · Bi-horaire · Impact | La structure du réseau |

Mono-horaire repasse la structure à Simple ; pour garder Impact, choisissez-le avec « Structure tarifaire ».

**Services** :

| Service | Effet |
|---|---|
| `foxcat_energy.save_settings_profile` | Exporte les réglages EMS dans `/config/foxcat_energy/profiles/` |
| `foxcat_energy.load_settings_profile` | Valide puis applique un profil |
| `foxcat_energy.reset_settings` | Restaure les valeurs par défaut du moteur et des machines |

## 16. Dashboards et cartes

FoxCat génère ses dashboards YAML dans `/config/foxcat_energy/` : `dashboard.yaml` (tablette / PC) et `dashboardmob1.yaml` (mobile). Les fichiers existants ne sont jamais écrasés au démarrage ; le bouton **Régénérer le dashboard FoxCat** force la régénération avec sauvegarde `.bak`. Les versions tablette et mobile se choisissent indépendamment, et la **fusion à trois sources** conserve vos personnalisations non conflictuelles. Cartes requises : `custom:button-card`, `custom:apexcharts-card`, `card-mod`.

| Fichier | Contenu |
|---|---|
| [`docs/cartes/vue_couts.yaml`](docs/cartes/vue_couts.yaml) | Vue « Coûts » tablette |
| [`docs/mobile/cartes/vue_couts_mobile.yaml`](docs/mobile/cartes/vue_couts_mobile.yaml) | Vue « Coûts » mobile |
| [`docs/cartes/comparateur_tarifs.yaml`](docs/cartes/comparateur_tarifs.yaml) | Carte markdown du comparateur |
| [`docs/automations/etage_decalage_vtherm.yaml`](docs/automations/etage_decalage_vtherm.yaml) | Automatisation du décalage de chauffage |

> **Détail des algorithmes** : pas à pas, seuils et sécurités de chaque module dans [`docs/algorithmes/`](docs/algorithmes/README.md), avec le [rapport d'anomalies](docs/algorithmes/ANOMALIES.md).

## 17. Sécurité et limites

FoxCat peut piloter des équipements électriques. Validez capteurs, polarités, actionneurs et limites physiques avant d'activer la régulation. Gardez les protections matérielles en place : le logiciel n'est **pas** un dispositif de sécurité certifié. **Retour arrière immédiat** : coupez « Régulation FoxCat active », libérez l'onduleur à 100 %, puis restaurez la version précédente.

Le dépôt est en développement actif. Tests et simulations ne remplacent pas une validation sur l'installation réelle.

## 18. Dépôt, tests et licence

```text
custom_components/foxcat_energy/   intégration (domain/, runtime/, trading/, dashboard/…)
tests/                             tests unitaires
docs/                              plans, cartes, automatisations, archives par version
docs/algorithmes/                  audit des algorithmes, page par domaine, et rapport d'anomalies
trash/                             fichiers obsolètes mis de côté (voir trash/LISEZMOI.md)
MANUEL.md                          configuration pas à pas
CHANGELOG.md                       journal des versions
```

Licence : voir [`Licence.md.txt`](Licence.md.txt).
