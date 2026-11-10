# FoxCat Energy

> **Home Energy Management System (HEMS) pour Home Assistant**
>
> FoxCat Energy est un système de gestion énergétique résidentielle conçu pour **valoriser localement l’énergie disponible**, piloter les charges flexibles et adapter la production photovoltaïque lorsque la réinjection n’est pas économiquement intéressante.

## Qu’est-ce que FoxCat Energy exactement ?

FoxCat Energy n’est pas un simple tableau de bord énergétique, ni une automatisation unique.

C’est un **moteur de gestion énergétique** qui observe en permanence la maison, prend des décisions selon un mode EMS choisi par l’utilisateur, commande les équipements autorisés et vérifie que les ordres ont réellement produit l’effet attendu.

Son objectif n’est pas de produire le maximum à tout prix.

La logique recherchée est :

```text
Produire utilement
        ↓
Consommer localement
        ↓
Stocker l’énergie quand cela a du sens
        ↓
Déplacer les usages flexibles
        ↓
Limiter la production excédentaire
        ↓
Éviter une réinjection sans valeur
```

FoxCat Energy a été pensé en priorité pour les installations où la réinjection peut devenir peu intéressante, nulle ou coûteuse, notamment avec compteur communicant et contrats dynamiques.

Il peut néanmoins fonctionner dans plusieurs contextes tarifaires.

---

# Philosophie générale

FoxCat Energy repose sur quelques principes fondamentaux.

### EMS1 reste souverain

EMS1 représente la couche temps réel.

Il :

- mesure ;
- vérifie la validité des données ;
- applique les sécurités ;
- décide ;
- commande ;
- vérifie l’exécution ;
- corrige si nécessaire.

Une décision importante ne doit pas être considérée comme exécutée tant que son effet physique n’a pas été confirmé.

### EMS2 reste prédictif et consultatif

EMS2 peut exploiter :

- prévisions solaires ;
- prix futurs ;
- historique ;
- présence ;
- comportement thermique ;
- tendances de consommation.

Mais EMS2 **ne commande pas directement les équipements**.

Il conseille EMS1 sans contourner les règles de sécurité ni les décisions déterministes.

### Les usages utiles passent avant le bridage

Avant de réduire la puissance photovoltaïque, FoxCat cherche d’abord à utiliser intelligemment l’énergie disponible.

Exemples :

- eau chaude sanitaire ;
- lave-linge ;
- sèche-linge ;
- lave-vaisselle ;
- batterie domestique ;
- futures charges pilotables.

Le PRI devient la dernière couche d’ajustement lorsque le surplus n’a plus d’usage utile.

---

# Architecture logique

```text
CAPTEURS
   │
   ▼
VALIDATION DES DONNÉES
   │
   ▼
CONTEXTE TARIFAIRE
   │
   ▼
MODE EMS
   │
   ▼
ARBITRE ÉNERGÉTIQUE
   ├── Boiler
   ├── Machines
   ├── Batterie
   ├── Futures charges
   └── Onduleur (moteur PRI)
   │
   ▼
EXÉCUTION
   │
   ▼
ACK COMMANDE
   │
   ▼
ACK PHYSIQUE
   │
   ▼
ACK ÉNERGÉTIQUE
```

---

# Modes EMS

## Économie énergie

Le mode **Économie énergie** devient un mode hybride.

Il ne pilote pas seulement le boiler : il arbitre entre les charges utiles et la production photovoltaïque.

Principe :

```text
Surplus solaire
   ↓
Charge utile disponible ?
   ├── Oui → utiliser le surplus
   └── Non → réduire progressivement l’onduleur
```

Le boiler conserve les règles thermiques définies par FoxCat :

- confort ECS ;
- stockage solaire opportuniste ;
- limites de température ;
- cycles minimums ;
- respect des plages tarifaires ;
- protections physiques.

Le PRI agit en parallèle pour éviter une réinjection inutile.

---

## ECS solaire

Le mode **ECS solaire** reste volontairement centré sur le stockage thermique.

Objectif :

- maximiser l’utilisation du solaire dans le boiler ;
- garantir le service ECS ;
- respecter les limites thermiques ;
- conserver les règles déjà validées.

Ce mode ne doit pas être transformé silencieusement en stratégie de bridage photovoltaïque.

---

## Zéro injection

Le mode **Zéro injection** prend le réseau comme vérité principale.

La consommation maison reste une information utile, mais elle ne constitue plus la cible principale du PRI.

La variable prioritaire devient :

```text
Réinjection réseau réelle
```

Principe de régulation :

```text
Réinjection trop élevée
→ descente PRI de 10 %

Nouvelle mesure réseau
→ validation / ACK

Réinjection encore présente
→ nouvelle descente

Prélèvement devenu trop important
→ remontée possible

Remontée provoquant à nouveau trop de réinjection
→ rollback
```

Le système doit accepter qu’un zéro parfait ne soit pas toujours techniquement optimal.

FoxCat peut donc fonctionner en :

- **zéro injection strict** lorsque c’est possible ;
- **zéro injection partiel / best effort** lorsqu’un palier supplémentaire provoquerait trop de prélèvement réseau.

---

## Prix dynamique

Le mode **Prix dynamique** est le mode financier de FoxCat Energy.

Il doit analyser :

- prix actuel ;
- prix suivant ;
- minimum du jour ;
- maximum du jour ;
- moyenne ;
- tendance ;
- prix de réinjection ;
- intérêt économique du stockage ;
- intérêt économique du bridage.

Priorité générale :

```text
1. Autoconsommer le solaire
2. Stocker l’énergie utile
3. Exploiter un prix réseau très bas ou négatif
4. Comparer la valeur de l’injection
5. Réduire la production si l’injection n’est pas intéressante
6. Libérer davantage l’onduleur si l’injection devient économiquement favorable
```

### Prix négatif

Lorsque le prix d’achat devient négatif, FoxCat peut volontairement **tirer sur le réseau** si cela crée un avantage économique.

Exemple :

```text
Prix réseau négatif
+ capacité thermique disponible
+ sécurités OK
→ charge du boiler depuis le réseau
```

À terme, cette logique pourra également s’appliquer à d’autres stockages :

- batterie domestique ;
- véhicule électrique ;
- charge variable ;
- autres équipements capables d’absorber temporairement de l’énergie.

---

## Manuel

Le mode **Manuel** rend réellement la main à l’utilisateur.

Dans ce mode :

- pas de stratégie boiler automatique ;
- pas de PRI automatique ;
- pas de gestion automatique des machines ;
- pas d’arbitrage tarifaire actif.

FoxCat continue toutefois :

- à mesurer ;
- à afficher ;
- à journaliser ;
- à conserver les sécurités critiques.

Les protections thermiques ou matérielles ne doivent jamais disparaître simplement parce que le mode Manuel est sélectionné.

---

# Régimes tarifaires

Le mode EMS et le régime tarifaire sont deux notions distinctes.

FoxCat Energy prévoit trois grandes familles.

## Compensation

Mode destiné aux installations encore soumises à un mécanisme de compensation.

Les coûts journaliers doivent être considérés comme indicatifs car une compensation annuelle ne peut pas être représentée correctement par un simple coût instantané.

## HP / HC

Le régime bi-horaire utilise :

- prix heures pleines ;
- prix heures creuses ;
- plages horaires configurables ;
- prix fixe éventuel de réinjection.

Les horaires ne doivent pas être codés définitivement dans le moteur afin de permettre l’utilisation de FoxCat chez plusieurs gestionnaires de réseau.

### Évolution prévue

À terme, l’utilisateur pourra choisir entre :

- saisie manuelle du prix HP ;
- saisie manuelle du prix HC ;
- entité Home Assistant donnant le prix HP ;
- entité Home Assistant donnant le prix HC.

Le fonctionnement deviendra donc similaire à la configuration du tarif dynamique.

---

## Dynamique

Le régime dynamique repose sur les entités de prix fournies par le contrat ou l’intégration tarifaire utilisée.

FoxCat exploite notamment :

- prix d’achat courant ;
- prix suivant ;
- minimum ;
- maximum ;
- moyenne ;
- prix ou valeur de réinjection.

---

# Gestion des cycles protégés

Une machine dont le cycle est protégé ne doit jamais être interrompue par FoxCat.

Exemples :

- lave-linge ;
- sèche-linge ;
- lave-vaisselle.

### Correction de stratégie prévue

La présence d’un cycle protégé **ne doit pas interdire automatiquement le fonctionnement du boiler**.

La bonne logique est :

```text
Machine protégée en fonctionnement
        ↓
Mesurer le surplus restant
        ↓
Surplus suffisant pour alimenter le boiler ?
        ├── Oui → boiler autorisé
        └── Non → boiler différé ou arrêté selon la stratégie active
```

La machine reste prioritaire parce que son cycle ne peut pas être interrompu, mais le boiler peut fonctionner simultanément lorsque la puissance disponible le permet.

Cette évolution remplace la logique trop restrictive :

```text
Machine active → Boiler interdit
```

par :

```text
Machine active → Boiler possible si énergie réellement disponible
```

**Statut : évolution fonctionnelle à intégrer / À TESTER.**

---

# Onduleur SolarEdge (moteur PRI)

FoxCat Energy utilise le PRI comme actionneur de limitation de puissance photovoltaïque.

Pour l’installation de référence :

- onduleur nominal : 4 000 W ;
- 11 niveaux ;
- de 0 à 100 % ;
- pas de 10 % ;
- environ 400 W par palier.

La logique recherchée n’est pas de calculer une puissance idéale théorique puis de l’imposer aveuglément.

Le réseau sert de retour réel :

```text
Décision
→ commande RRCR
→ ACK RRCR
→ mesure réseau
→ correction
```

La stabilité est prioritaire sur la recherche obsessionnelle de 0 W exact.

---

# Vers un EMS extensible

FoxCat Energy doit évoluer vers une architecture où les équipements ne sont plus codés en dur.

L’utilisateur pourra progressivement ajouter ses propres appareils.

Exemples :

- boiler ;
- lave-linge ;
- sèche-linge ;
- lave-vaisselle ;
- batterie domestique ;
- charge variable ;
- autres charges flexibles.

Chaque appareil pourra être décrit par ses capacités.

Exemple conceptuel :

```text
Nom : Batterie maison
Type : Stockage électrique
Puissance max : 5 000 W
Puissance variable : Oui
Interruption autorisée : Oui
Énergie minimale à conserver : 20 %
Priorité EMS : 2
Compatible prix négatif : Oui
Compatible surplus solaire : Oui
```

Autre exemple :

```text
Nom : Lave-linge
Type : Cycle protégé
Puissance : 2 500 W
Puissance variable : Non
Interruption autorisée : Non
Démarrage flexible : Oui
Priorité EMS : 1
```

Le moteur ne devra donc plus raisonner uniquement en fonction de noms d’appareils, mais en fonction de **capacités énergétiques**.

---

# Modèle futur des appareils

Une architecture générique pourra décrire chaque équipement avec des propriétés telles que :

- type d’appareil ;
- puissance nominale ;
- puissance minimale ;
- puissance maximale ;
- charge variable ou tout-ou-rien ;
- cycle interruptible ou protégé ;
- priorité ;
- plage de fonctionnement ;
- autorisation réseau ;
- autorisation solaire ;
- compatibilité prix négatif ;
- capacité de stockage ;
- niveau minimal ;
- niveau maximal ;
- entité de puissance ;
- entité de commande ;
- entité d’état.

Le moteur EMS pourra ensuite construire sa stratégie à partir de ces propriétés.

```text
APPAREILS CONFIGURÉS
        ↓
CAPACITÉS
        ↓
PRIORITÉS
        ↓
CONTRAINTES
        ↓
MODE EMS
        ↓
ARBITRAGE
```

C’est cette évolution qui permettra à FoxCat Energy de devenir un produit adaptable à plusieurs maisons sans réécrire les stratégies pour chaque installation.

---

# Évolution du projet

## V1.0

Première encapsulation du moteur FoxCat dans un custom component Home Assistant.

Objectifs :

- sortir progressivement des automatisations YAML ;
- centraliser la logique ;
- séparer décision et exécution ;
- conserver EMS1 souverain.

## V1.1

Évolutions principales :

- amélioration du PRI ;
- gestion machines ;
- renommage et harmonisation des entités en français ;
- préparation du dépôt HACS.

## V1.2

Restructuration générale :

- clarification des modes EMS ;
- ECO hybride ;
- Zéro injection centré sur le réseau ;
- mode Prix dynamique renforcé ;
- suppression du mode Confort ;
- distinction entre stratégie EMS et régime tarifaire ;
- ajout de la tarification HP/HC ;
- possibilité de tirer sur le réseau lorsque le prix devient négatif.

## V1.2.1

Correctif structurel du flux de configuration Home Assistant.

Objectif :

- rendre le `config_flow` et la reconfiguration fiables ;
- réduire les dépendances chargées trop tôt ;
- préserver les stratégies énergétiques existantes.

## V1.2.2

Ajout d’une configuration dédiée aux tarifs HP/HC.

Objectifs :

- prix HP ;
- prix HC ;
- prix fixe de réinjection ;
- plages HP configurables ;
- capteurs tarifaires dédiés.

## Prochaines évolutions

### Réalisé en V1.3.0 — Arbitrage machine / boiler

Une machine protégée ne bloque plus systématiquement le boiler. Le boiler est autorisé lorsque le surplus réellement disponible couvre sa puissance, avec validation stable sur deux trames avant démarrage.

### Réalisé en V1.3.0 — Gestionnaire de machines ON/OFF extensibles

FoxCat permet désormais d’ajouter, modifier et supprimer des machines ON/OFF, chacune avec identifiant stable, nom, prise, cycle protégé optionnel, capteur de puissance optionnel, gestion automatique et deux plages horaires.

### Priorité suivante — Charges flexibles ON/OFF génériques

Étendre l’arbitrage à des charges comme second boiler, résistance d’appoint, pompe ou chauffage de stockage, avec puissance nominale, priorité, autorisation réseau, durée minimale et stratégie par mode.

### Étape future — Charges variables et stockage

Ajouter batteries domestiques, bornes VE, charges modulables et stockage avec un arbitre énergétique multi-appareils.

### Étape future — Moteur économique

Comparer coût d’achat, valeur d’autoconsommation, valeur d’injection, intérêt du stockage, coût du bridage et bénéfice d’un prix négatif.

---

# Statuts de développement

FoxCat Energy distingue volontairement plusieurs niveaux de maturité.

| Statut | Signification |
|---|---|
| `IDÉE` | Principe envisagé |
| `À TESTER` | Implémenté ou défini mais non validé sur le terrain |
| `TEST` | En cours d’essai |
| `VALIDÉ` | Comportement confirmé |
| `UPGRADE` | Amélioration d’un comportement validé |
| `DOWNGRADE` | Régression ou retour vers une version plus simple |
| `ROLLBACK` | Retour volontaire à une version antérieure |
| `ABANDONNÉ` | Piste volontairement écartée |

Aucune fonction ne doit être considérée comme validée uniquement parce qu’elle compile ou fonctionne en simulation.

---

# Principe de compatibilité

Lors d’une évolution de FoxCat Energy :

- les fonctions validées doivent être conservées ;
- aucune sécurité ne doit être supprimée silencieusement ;
- aucune logique de priorité ne doit disparaître sans décision explicite ;
- les migrations doivent être documentées ;
- un rollback doit rester possible.

Le développement suit donc le principe :

> **Une nouvelle version est une extension contrôlée de la baseline précédente, pas une réécriture simplifiée.**

---

# Vision

FoxCat Energy doit devenir un EMS résidentiel capable de s’adapter à la maison dans laquelle il est installé.

Il ne doit pas uniquement connaître un boiler ou trois machines spécifiques.

Il doit comprendre :

- quelles charges sont disponibles ;
- lesquelles peuvent être interrompues ;
- lesquelles doivent terminer leur cycle ;
- lesquelles peuvent moduler leur puissance ;
- lesquelles peuvent stocker de l’énergie ;
- quel est le coût de l’électricité ;
- quelle est la valeur de l’injection ;
- quelle quantité de solaire est disponible ;
- quel usage apporte le plus de valeur à l’instant présent.

L’objectif final est simple :

> **Utiliser chaque kWh là où il apporte le plus de valeur, tout en conservant le confort, les sécurités et la souveraineté locale de l’installation.**

---

## État du projet

FoxCat Energy est actuellement un projet en développement actif.

Les fonctions énergétiques doivent être validées sur installation réelle avant d’être considérées comme stables pour une diffusion large.

**Projet : FoxCat Energy / FoxCat Energy Box**  
**Plateforme : Home Assistant**  
**Architecture : EMS1 souverain + EMS2 prédictif**  
**Orientation : autoconsommation, zéro injection, tarification dynamique et gestion intelligente des charges**


## V1.3.0 — Machines extensibles

- Les machines ON/OFF ne sont plus limitées au lave-linge, sèche-linge et lave-vaisselle.
- Ajout/modification/suppression depuis les options FoxCat Energy.
- Chaque machine possède un identifiant stable, un nom, une prise, un cycle protégé optionnel, un capteur de puissance optionnel, une gestion automatique et deux plages horaires.
- Les trois machines historiques sont migrées automatiquement tant qu’aucune liste V1.3 n’a été enregistrée.
- Un cycle protégé ne bloque plus le chauffe-eau par principe : le chauffe-eau est autorisé si le surplus réseau réel, après charge de la machine, couvre sa puissance. La décision de démarrage exige deux trames cohérentes.
- Le mode Manuel ne commande aucune prise machine.


## Délestage haute consommation (1.3.1)

FoxCat peut détecter une puissance maison durablement élevée et suspendre temporairement les charges variables afin de limiter les pointes, par exemple pendant la préparation des repas. La fonction est désactivée par défaut. Les seuils et temporisations sont réglables via les entités `number`. Un cycle machine protégé déjà actif n’est jamais interrompu. Le boiler est arrêté pendant le délestage, les machines marquées délestables sont coupées hors cycle, et le PRI est libéré à 100 % afin de maximiser la production photovoltaïque disponible. Le retour est temporisé et utilise un seuil inférieur au seuil de déclenchement. Le mode Manuel n’applique pas ce délestage automatique.
