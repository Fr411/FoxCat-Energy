# FoxCat Energy

**FoxCat Energy** est une intégration Home Assistant de gestion énergétique résidentielle (EMS, *Energy Management System*). Elle observe la maison en continu, valorise localement l'énergie solaire, pilote le chauffe-eau, les machines et l'onduleur, protège le raccordement, et chiffre en euros ce que coûte et ce que rapporte chaque kWh.

| | |
|---|---|
| Version de l'intégration | **1.7.703** |
| Home Assistant minimal | **2025.1.0** |
| Domaine | `foxcat_energy` |
| Langue de configuration | Français |

Pour installer et configurer pas à pas, lisez le **[Manuel](MANUEL.md)**. Ce document-ci explique **comment FoxCat fonctionne**. Les versions sont résumées dans le [journal des versions](JOURNAL_VERSIONS.md) et détaillées dans le [changelog](CHANGELOG.md).

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
- **Confort** : même stratégie boiler et même réduction de puissance de l'onduleur qu'Éco, toutes sécurités conservées. La différence est dans le planificateur de charges flexibles : il accepte moins d'attente (6 h au plus) et exige une économie plus grande (0,10 €) pour reporter un démarrage.
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

Réglages utiles (appliqués à la décision économique et aux recommandations des machines) : horizon, seuil de position « favorable » (30 % par défaut), seuil de pic, durée favorable maximale (4 h), charge réseau quand le prix devient négatif.

### Coupure Internet : fonctionnement local

Le cerveau de FoxCat tourne dans Home Assistant : mesures, boiler, onduleur et machines utilisent le réseau local. Seuls les prix de bourse, la prévision solaire en ligne et la tâche IA dépendent d'Internet. Les contrats fixes, bi-horaires et Impact n'en ont jamais besoin.

- **Tampon des prix.** Pour les sources Dynamique Day-Ahead et Intégration externe, FoxCat enregistre à chaque mise à jour la courbe d'achat et de réinjection (36 h devant, 3 h derrière) dans le stockage de Home Assistant. Il survit à un redémarrage. Les prix du lendemain étant publiés vers 14 h, une coupure en soirée laisse en général de 24 à 36 h de plan de route.
- **Hors ligne avec tampon.** Quand l'entité de prix devient indisponible, le prix actuel, le prix suivant et le prix de réinjection sont lus dans le tampon. Les décisions Day-Ahead continuent.
- **Tampon épuisé.** FoxCat n'estime aucun prix. La décision économique devient « Prix indisponible » et les machines différées ne démarrent plus. Le boiler dynamique passe en repli confort : chauffe réseau jusqu'à 45 °C seulement (reprise à 43 °C), jamais de BOOST réseau à 65 °C. Le BOOST solaire reste prioritaire.
- **Capteur « Flux de prix ».** États `EN_LIGNE`, `TAMPON`, `DEGRADE` et `LOCAL`, avec la fin du tampon (`buffer_until`) et les heures restantes. Le journal signale chaque changement.
- **Limites.** La comptabilité compte 0 € d'achat quand aucun prix n'existe et ne rattrape pas les prix au retour d'Internet. Forecast.Solar et la tâche IA solaire échouent hors ligne. Détail : [prix dynamiques](docs/algorithmes/05_prix_dynamiques.md).

### Mode Backup : Internet coupé

FoxCat sonde Internet toutes les 30 secondes (connexion TCP vers des résolveurs publics, rien n'est envoyé). Après la durée réglée sans connexion (2 minutes par défaut), le capteur **« Internet en ligne »** passe à hors ligne et le **mode Backup** s'enclenche :

- **Machines** : les prises restent alimentées ; fenêtres horaires, prix et planificateur sont ignorés.
- **Boiler** : **coupé** pendant toute la coupure, ballon froid compris ; il reprend sa stratégie normale au retour d'Internet. Une commande utilisateur « forcer la marche » reste prioritaire.
- **Onduleur** : plus bridé, sauf avec la politique « Zéro injection ».
- **Mémoire** : l'état des prises est enregistré avant la coupure et rétabli au retour d'Internet (après 60 secondes de connexion stable), sans jamais couper un cycle en cours.
- **Sécurité maintenue** : délestage du disjoncteur.

Interrupteur « Mode Backup si Internet coupé » (actif par défaut) et réglage de la durée. En mode Manuel ou régulation coupée, FoxCat ne commande rien. Pendant le Backup, le tampon de prix ne guide plus les décisions ; il continue d'alimenter l'affichage et la comptabilité. Détail : [prix dynamiques](docs/algorithmes/05_prix_dynamiques.md).

### Alertes de panne

FoxCat surveille sa propre santé et notifie ce qui ne fonctionne pas. **Critiques** : mesures ou métronome perdus, boiler en surchauffe, sonde du boiler ou de sécurité indisponible, relais de l'onduleur illisibles, commande en échec. **Majeures** : capteur principal silencieux, prix indisponibles, Internet coupé, prise de machine indisponible, délestage en cours, ancienne automatisation active, calcul en erreur, entité introuvable. Une alerte apparaît après 2 minutes (surchauffe et délestage : tout de suite) et disparaît après 60 secondes de retour stable.

**Sonde du boiler indisponible** : FoxCat n'assimile jamais l'absence de mesure à 0 °C. Dès que la sonde de température du boiler est illisible, toute commande de chauffe est refusée (y compris celle de l'utilisateur) et un boiler en train de chauffer est arrêté ; la chauffe reprend 60 secondes après le retour continu de la sonde. Au démarrage de Home Assistant, elle attend donc la première lecture.

Sorties : capteur **« Santé FoxCat »** (`OK`, `MAJEUR`, `CRITIQUE`, avec la liste), capteur binaire **« Alerte de panne FoxCat »**, une **notification** dans Home Assistant par alerte, et l'événement `foxcat_energy_alert` pour envoyer un message sur téléphone (exemple : `docs/automations/alerte_panne_foxcat.yaml`). Catalogue complet : [santé et alertes](docs/algorithmes/10_sante_alertes.md).

### Publication des prix

Une entité (par exemple « prix de demain disponible ») déclenche la relecture des prix, avec un service optionnel (par exemple `be_electricity_prices.refresh`), appelé au plus **une fois toutes les 10 minutes**.

### Ce que FoxCat expose

Flux de prix (en ligne, tampon local, repli), prix d'achat actif et suivant, valeur économique de la réinjection, période, statut du prix (avantageux / normal / élevé), prix négatif actif, position et rang sur la courbe, tendance, meilleur prix et créneau futurs, coût et valeur instantanés (€/h), solde réseau instantané.

## 6. Comparateur de tarifs et coûts réseau

**Comparateur.** FoxCat enregistre la consommation et les prix au quart d'heure (stockage séparé, 62 jours) et **rejoue chaque tarif configuré** sur cette consommation réelle. Deux capteurs, « Comparateur de tarifs • Aujourd'hui » et « • Ce mois », donnent le tarif le moins cher, le coût net de chaque tarif et l'écart avec le tarif actuel (négatif = moins cher). Les tarifs « actuel » et « contrat saisi » sont ajoutés automatiquement.

- Modèles belges prédéfinis : Wallonie mono, bi-horaire 2026, Impact. Chargement automatique selon la région.
- Tarifs personnalisés en JSON, copiables d'une installation à l'autre.
- **Comparaison à comportement constant** : le pilotage de FoxCat n'est pas rejoué. Un tarif dynamique serait en réalité encore meilleur si FoxCat déplaçait vos charges.
- Les créneaux sans prix connu sont signalés au lieu d'être inventés.

**Coûts réseau et prosumer.** Ils dépendent de votre gestionnaire de réseau, pas de votre fournisseur : le comparateur les applique **de la même façon à tous les tarifs**, si bien que l'écart ne reflète que le prix de l'énergie.

- *Terme capacitaire* : forfait annuel selon la puissance (Bruxelles) ou **moyenne des pointes mensuelles au quart d'heure sur au plus 12 mois, chacune au minimum 2,5 kW** (Flandre, comme Fluvius). **Wallonie : aucun terme capacitaire** (le tarif Impact est un tarif par périodes ECO / MEDIUM / PIC). Règles et sources dans [`docs/algorithmes/04_tarification.md`](docs/algorithmes/04_tarification.md) § 5.1.
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
- **Heures creuses (bi-horaire)** : démarrage sur le réseau seulement au dernier failback (voir ci-dessus). Les anciens réglages d'« agressivité solaire » sont **inactifs**.
- **Dynamique** : arbitrage thermique selon le prix. Un modèle (volume, puissance, eau froide à 15 °C) estime la durée de chauffe et réserve les créneaux les moins chers.
- **Délestage** : le boiler peut être coupé pendant une pointe de consommation.
- **Commande forcée** (forcer la marche ou l'arrêt) : elle expire après 6 h par défaut (réglable, 0 = illimitée) et rend la main à l'EMS. Les vitesses de chauffe (10 °C/h) et de refroidissement (0,5 °C/h) servent au calcul du dernier failback et sont réglables.

## 9. Onduleur et PRI / RRCR

Le **PRI** réduit la puissance de l'onduleur par quatre relais **RRCR** (L1 à L4, un code de niveau). FoxCat s'en sert quand le surplus n'a plus d'usage utile ou que la réinjection est indésirable.

- Algorithme à pas (100 à 1 000 W) avec scoring import/réinjection, tolérances et fenêtres « optimal / acceptable ».
- Contrôle par **accusé physique** : la puissance de l'onduleur ou du réseau doit bouger comme prévu.
- Un capteur de **puissance live** de l'onduleur est facultatif et purement informatif.
- **Retour réel des relais (facultatif)** : quatre entités « Retour réel L1 à L4 » reçoivent l'état réel des relais renvoyé par le contrôleur (ex. Siemens LOGO, sorties réseau NQ9 à NQ12). Sans elles, l'accusé RRCR relit seulement l'état Home Assistant des interrupteurs, c'est-à-dire la dernière commande envoyée. Avec elles, FoxCat pose un **ACK LOGO** après chaque commande (`OK` si le retour correspond au code commandé, `FAILED` s'il diffère, `ABSENT` si illisible, `PENDING` en attente, `NON_CONFIGURE` sans retour) et publie la **disponibilité de la commande** : `DISPONIBLE`, `DEGRADE` (retour lisible mais différent de la commande), `INDISPONIBLE` (retour illisible) ou `NON_CONFIGURE`. Un champ optionnel **« LOGO en ligne »** (capteur binaire de connexion du contrôleur) complète les retours : s'il n'est pas `on`, la commande est `INDISPONIBLE` ; seul, il donne `DISPONIBLE` quand il est `on`. **Garde LOGO** : tant que le contrôleur est hors ligne ou que le retour est illisible (`INDISPONIBLE`), la garde PRI suspend les décisions et l'envoi des commandes (raison `logo_indisponible`) ; un simple écart (`DEGRADE`) est seulement signalé. « Libérer l'onduleur à 100 % » et le fail-safe ne passent pas par cette garde.
- Actif en **Éco et Confort**, jamais en Manuel ; passer en Manuel libère l'onduleur à 100 % si le PRI est activé.
- Niveau manuel disponible en mode Manuel ; « Libérer l'onduleur à 100 % » est le retour arrière immédiat. Le code RRCR se lit **L4 L3 L2 L1** (`1000` = L4 fermé). Dans le dashboard 1.8.0, la vue Onduleur propose des **contacts L1 à L4** cliquables (confirmation à chaque appui) et des boutons de niveau passant par le sélecteur FoxCat « Niveau réduction puissance onduleur manuel », qui relit le code et publie l'ACK RRCR. Les anciens boutons appelaient `script.pri_rrcr_forcer_un_niveau`, qui testait `input_select.ems_mode` (disparu) et refusait toute commande.
- Coupé automatiquement en fin de journée solaire (seuil et confirmation réglables).

## 10. Machines

- **Lave-linge, sèche-linge, lave-vaisselle** (historiques) et **machines extensibles** : chaque machine est un switch pilotable ou un **CVC en télémétrie seule** (observé, comptabilisé séparément).
- **Fenêtre machines** : plage horaire pendant laquelle l'alimentation est autorisée.
- **Détection et protection de cycle** : une machine en cycle n'est jamais coupée en plein programme.
- **Apprentissage passif** : jusqu'à 30 cycles récents par machine mesurée.
- **Planificateur de charges flexibles** : décide du démarrage selon le surplus solaire et les prix. Il reste seul décideur de l'autorisation de démarrer, sauf si l'un des deux planificateurs ci-dessous est activé.
- **Planificateur dynamique** (tarif dynamique) : place chaque cycle sur les créneaux les moins chers avant l'échéance, avec des bandes de prix par rang (négatif, très bas, bas, normal, élevé, pic), le surplus solaire, la puissance parallèle limitée et un plan stable (réglage « stabilité du plan »). Les machines interruptibles prennent les N créneaux les moins chers.
- **Planificateur bi-horaire** (tarif HP/HC) : même moteur sur une courbe HP/HC de 36 h ; un cycle qui déborde sur les HP paie ses minutes HP, donc il attend les HC suivantes ; pas de report si HP et HC sont presque au même prix.
- Les deux planificateurs sont en **observation** par défaut (capteurs « Planificateur dynamique » et « Planificateur bi-horaire ») ; leur interrupteur « … pilote les machines » leur confie l'autorisation de démarrage. Un cycle protégé continue toujours, l'écrêtage bloque les nouveaux départs, le mode Manuel donne une recommandation seule. **Synchronisation avec les prises** : dès que « départ autorisé », « plage ouverte » ou « gestion de la machine » change, FoxCat relance la réconciliation des prises (au plus une fois par minute, jamais en mode Manuel ; pas de scrutation, une prise allumée à la main n'est pas coupée sans changement du plan). Chaque machine du plan expose `socket_state`, `socket_expected` et `socket_sync` (`OK`, `ECART`, `INDISPONIBLE`, `HORS_PILOTE`, `NON_GERE`) ; ces attributs ne sont pas encore affichés dans les vues. Le boiler garde sa logique propre. Détail : [`docs/algorithmes/07_machines_planificateur.md`](docs/algorithmes/07_machines_planificateur.md).
- **Phase du réseau** par machine (L1, L2, L3) pour le calcul de charge.
- Une machine peut être marquée **délestable**.

## 11. Chauffage : décalage de consigne

Fonction **désactivée par défaut**. FoxCat calcule un décalage en °C (0 à 2 °C par pas de 0,5 °C par défaut) selon le surplus solaire et la présence, et le publie dans le capteur « Chauffage • Décalage de consigne », avec un capteur « Statut » qui donne la raison. **Une automatisation Home Assistant** applique ce décalage aux presets de **Versatile Thermostat** : FoxCat n'écrit jamais dans les `climate.*` ni dans les `number.*`.

Le **surplus** se base sur la **réinjection réelle** : export − import − marge de réserve, plus la consommation déjà accordée aux pas en cours (pas accordés × surplus par pas, car elle a déjà été prélevée sur la réinjection). La consommation normale d'une PAC, même couverte en partie par le solaire, n'est jamais du surplus : sans réinjection, aucun pas n'est accordé. Le capteur « Surplus calculé » peut être négatif. Le décalage est recalculé **à chaque trame réseau**, seulement quand la fonction est activée (le capteur « Statut » indique `calcule_a` et `calcule_par`). Règles : anti-yoyo (300 s avant toute augmentation), un pas accordé est conservé tant que le surplus reste à 60 % du seuil, baisse immédiate si l'import dépasse 300 W, garde sur la puissance du groupe de climatisation. Option « uniquement maison vide ». Tout est créé par FoxCat, sans helper à créer à la main. Exemple d'automatisation : [`docs/automations/etage_decalage_vtherm.yaml`](docs/automations/etage_decalage_vtherm.yaml).

Le menu permet aussi de déclarer des **systèmes de chauffage** (pompes à chaleur : groupe extérieur, et jusqu'à 5 unités intérieures pour une PAC air/air).

## 12. Protection du raccordement

Quand la puissance dépasse un seuil, FoxCat **délestera** les charges non essentielles puis les rétablit après un retour sous le seuil de réarmement.

- Seuil : % du calibre du disjoncteur (90 % par défaut) ou seuil absolu en watts.
- Réseau mono, tri ou tétra. Si vous avez des intensités par phase, FoxCat prend la plus élevée.
- Mesure comparée (`peak_measure_basis`) : **consommation maison** par défaut (comportement historique) ou import réseau (évite de délester quand le solaire couvre la charge).
- Confirmation sur plusieurs trames avant déclenchement, **réarmement toujours au moins 5 % sous le déclenchement** pour éviter les oscillations.
- Actions : couper le boiler, couper les machines délestables (jamais en plein cycle), libérer l'onduleur à 100 %, bloquer les nouveaux démarrages flexibles, assistance V2H.

### Sans capteur d'intensité par phase

Un disjoncteur déclenche sur la phase la plus chargée, pas sur le total. Sans courant par phase, FoxCat ne peut pas savoir quelle phase est en tête. Il travaille donc avec ce qu'il a :

- **Tensions mesurées** (facultatives) : phase-neutre L1, L2, L3 (≈ 230 V) et entre lignes L1-L2, L2-L3, L3-L1 (≈ 400 V). FoxCat recoupe les deux familles, ignore les valeurs aberrantes et retombe sur la tension nominale sans mesure. La tension obtenue sert à calculer la capacité du disjoncteur et l'intensité. L'ancien capteur de tension unique reste pris en compte s'il est le seul renseigné.
- **Coefficient de déséquilibre des phases** (1 par défaut, 3 au maximum) : il suppose que la phase la plus chargée porte K fois la charge moyenne. La capacité vue du total devient `A × V × phases ÷ K`. Exemple : 25 A, 3 phases, 230 V, K = 1,3 → capacité 13 269 W, déclenchement à 90 % ≈ 11 942 W, au lieu de 15 525 W avec K = 1. Il ne s'applique ni en monophasé ni quand des intensités par phase sont mesurées.
- **Valeurs réelles du délestage** : le capteur « Statut délestage haute consommation » expose en attributs la base de mesure, la puissance comparée, les seuils de déclenchement et de réarmement (et leur origine), les trames requises et leurs compteurs. C'est ce que lit la carte du dashboard.
- **Diagnostic** : les attributs de l'entité « Charge du disjoncteur principal » exposent l'intensité estimée et sa source, le coefficient appliqué, la tension utilisée et son origine (`nominal`, `phase`, `line` ou `phase+line`), la tension entre lignes et l'écart entre phases.

Les tensions améliorent la précision du calcul ; elles **ne détectent pas** une phase surchargée. Seul le coefficient en tient compte.

## 13. Batterie et véhicule électrique

- **Simulateur** de batterie domestique et de véhicule virtuels : désactivé par défaut, **sans commande physique**, isolé du registre réel. Il sert à estimer ce qu'apporterait un équipement avant de l'acheter. Les valeurs simulées sont distinguées des mesures réelles.
- **Arbitrage virtuel** à l'achat et à la revente tenant compte de l'écart de prix et du coût d'usure.
- **V2H physique** : fonction distincte, *opt-in*, avec commande configurée explicitement, réserve de mobilité obligatoire et interverrouillage avec le chauffe-eau de confort. Couper la régulation ou passer en Manuel arrête la décharge.

## 14. Prévisions, IA et planification

- **Prévisions solaires** (Forecast.Solar et capteurs de prévision) et **agent IA Home Assistant** (AI Task) facultatif. Le module est consultatif ; sans IA, FoxCat garde un repli déterministe.
- **Price Analyzer V2** : statistiques du jour et de demain, position et rang, fraîcheur et continuité des données, série complète exposée en attribut pour les graphiques.
- **Planificateur de charges flexibles** (V1.7.1) : décideur de l'autorisation de démarrer par défaut ; remplacé par le **planificateur dynamique** ou **bi-horaire** quand leur interrupteur est activé (voir section 10).
- **Optimiseur économique** et arbitrage de prévision solaire, activables séparément.

## 15. Entités, appareils et services

Les entités sont rangées en **13 appareils** : Mesures et sources · Tarification · **Planificateur** · Onduleur · Boiler · Chauffage · Machines · **Machine Learning** · Batterie et VE · Protection · Prévisions et IA · **Santé et alertes** · Système. Le Planificateur regroupe les planificateurs (charges flexibles, dynamique, bi-horaire), l'analyse de la courbe de prix (Day-Ahead, Price Analyzer, position et rang), l'optimiseur économique et leurs réglages ; Machine Learning, l'apprentissage passif des cycles ; Santé et alertes, les pannes, Internet, le mode Backup et le flux de prix. Les `entity_id` et `unique_id` sont stables : dashboards et automatisations existants continuent de fonctionner.

**Réglages inactifs.** Une vingtaine d'entités de réglage (par exemple « Agressivité solaire Bihoraire », « Charge réseau si prix dynamique négatif », plusieurs seuils PRI) ne sont lues par aucune stratégie active. Elles restent pour ne pas casser les tableaux de bord et les profils, mais elles sont créées **désactivées**, rangées en diagnostic et portent l'attribut `statut: inactif`. La liste est dans `INACTIVE_SETTINGS` (`const.py`) et dans [`docs/algorithmes/ANOMALIES.md`](docs/algorithmes/ANOMALIES.md) (A-03).

Principaux interrupteurs : Régulation FoxCat active, Boiler géré par FoxCat, Boiler autorisé en heures creuses, Réduction de puissance onduleur, Gestion de chaque machine, Délestage haute consommation, Analyse prédictive IA, Optimisation économique, Prédictif prix dynamique, Planificateur dynamique / bi-horaire pilote les machines, Décalage de consigne solaire, Résumé EMS persistant.

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

FoxCat génère ses dashboards YAML dans `/config/foxcat_energy/` : `dashboard.yaml` (tablette / PC) et `dashboardmob1.yaml` (mobile). Les fichiers existants ne sont jamais écrasés au démarrage ; le bouton **Régénérer le dashboard FoxCat** force la régénération avec sauvegarde `.bak`. Les versions tablette et mobile se choisissent indépendamment, et la **fusion à trois sources** conserve vos personnalisations non conflictuelles. Cartes requises : `custom:button-card`, `custom:apexcharts-card`, `card-mod`, et pour la version 1.8.0 `vertical-stack-in-card` (mobile : aussi `layout-card`/`masonry-layout` et `html-template-card`).

**Dashboards 1.9.0 (recommandés) : vue Planificateur.** Un onglet « Planificateur » (`dashboard_v1.9.0.yaml`) superpose sur une même frise 36 h le **tarif** (barres colorées par bande de prix, ou HP/HC en bi-horaire), les **fenêtres autorisées** de chaque machine (zones pointillées) et les **cycles planifiés** (barres pleines), avec le trait « Maintenant ». Les couloirs suivent la priorité : **1 Boiler, 2 Lave-vaisselle, 3 Lave-linge, 4 Sèche-linge** (rang de repli quand les priorités des machines sont égales ; une priorité réglée sur la machine prime). La vue lit le capteur « Planificateur dynamique » ou « Planificateur bi-horaire » selon le contrat. Le boiler est informatif : créneaux les moins chers en dynamique, heures creuses en bi-horaire. Les barres des cycles dessinent la **forme de consommation apprise** de la machine (Machine Learning) et les cartes indiquent « Appris sur N cycles · durée · énergie ». Les planificateurs utilisent durée, énergie et forme apprises à partir de 3 cycles mesurés. Aperçus : [`docs/PREVIEW_PLANIFICATEUR_DYNAMIQUE.png`](docs/PREVIEW_PLANIFICATEUR_DYNAMIQUE.png) et [`docs/PREVIEW_PLANIFICATEUR_BIHORAIRE.png`](docs/PREVIEW_PLANIFICATEUR_BIHORAIRE.png) (données de démonstration). Le **dashboard mobile 1.9.0** (`dashboard_mobile_v1.9.0.yaml`) reprend la même carte en mise en page téléphone, ouverte par la tuile « Planificateur » de l'Accueil ; les deux ajoutent une carte de réglages (interrupteurs « … pilote les machines », stabilité du plan).

**Dashboards 1.8.0.** Une version tablette / PC et une version mobile, livrées à l'installation (`dashboard_v1.8.0.yaml`, `dashboard_mobile_v1.8.0.yaml`). Tablette : Accueil, Énergie, **Flux** (pieuvre animée **Mina**, dont l'humeur suit le solaire, le réseau et la consommation), **Onduleur** (scène animée PV → onduleur → maison / réseau, oscilloscope triphasé, relais RRCR L1 à L4, table des 11 niveaux, mesures SolarEdge, **commande manuelle** réelle), Boiler animé, Machines, Chauffage, **Délestage haute consommation** (carte animée : jauge du disjoncteur, étapes surveillance / seuil dépassé / délestage / réarmement, charges délestables), Marche, Diagnostic, Technique, VE-Batterie. Les entités sont résolues par le registre FoxCat ; quelques entités propres à une installation (machines, capteurs de charges) restent écrites en clair et sont à adapter. Les vues Logger, Configuration, Coûts, Day-Ahead, Batterie+VE et Contrat de la 1.7.4 ne sont pas reprises (version 1.7.4 toujours sélectionnable). Non vérifié : le rendu sur une installation autre que celle de développement.

L'état du dashboard (version active, versions disponibles, dashboard personnalisé) est relu hors de la boucle d'événements de Home Assistant à chaque rafraîchissement du coordinateur (30 secondes au plus) et après un changement de version. Une modification manuelle du fichier apparaît donc avec ce délai. Les modèles d'appareils (`domain/loads/devices/*.yaml`) sont lus une seule fois au démarrage.

| Fichier | Contenu |
|---|---|
| [`docs/cartes/vue_couts.yaml`](docs/cartes/vue_couts.yaml) | Vue « Coûts » tablette |
| [`docs/mobile/cartes/vue_couts_mobile.yaml`](docs/mobile/cartes/vue_couts_mobile.yaml) | Vue « Coûts » mobile |
| [`docs/cartes/comparateur_tarifs.yaml`](docs/cartes/comparateur_tarifs.yaml) | Carte markdown du comparateur |
| [`docs/automations/etage_decalage_vtherm.yaml`](docs/automations/etage_decalage_vtherm.yaml) | Automatisation du décalage de chauffage |

> **Publier une release** : workflow GitHub Actions « Publier une release » (tag `V1.7.N` suivant calculé automatiquement, notes tirées du CHANGELOG), mode d'emploi dans [`docs/PUBLIER_UNE_RELEASE.md`](docs/PUBLIER_UNE_RELEASE.md).

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
CHANGELOG.md                       détail des changements
JOURNAL_VERSIONS.md                une ligne par version
```

Licence : voir [`Licence.md.txt`](Licence.md.txt).
