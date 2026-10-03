# FoxCat Energy

**EMS local pour Home Assistant — énergie, onduleur, Boiler, machines, tarification et optimisation économique.**

Version actuelle : **1.6.158**  
Base de développement : **1.6.157 Dynamic Arbitrage**  
Fonctionnement : **100 % local dans Home Assistant**

---


## V1.6.158 — Tarification cohérente, courbe Luminus & Accounting signé

Cette version corrige le socle financier de FoxCat sans modifier les moteurs sanctuarisés MachineCycleManager / Energy Bus / modes historiques hors tarification.

- **Luminus Dynamic devient la référence exclusive du régime Dynamique** : prix actuel, H+1, courbe `today/tomorrow` et réinjection.
- **Luminus ComfyFlex devient la référence exclusive du régime HP/HC** : prix HP, prix HC et prix de réinjection fixe/configuré.
- Le parseur Day-Ahead comprend désormais les champs Luminus `all_in` et `injection`; FoxCat sait donc réellement où il se trouve sur la courbe tarifaire connue.
- Ajout des capteurs **Position sur la courbe dynamique**, **Zone de la courbe dynamique**, **Avantage économique autoconsommation** et **Courbe tarifaire FoxCat**.
- La réinjection Luminus Dynamic est normalisée selon la convention réelle : **positif = revenu**, **négatif = coût d'injection**.
- Règle souveraine PRI : **si la réinjection dynamique est rémunératrice, le PRI est libéré à 100 %**, indépendamment du kill-switch prédictif.
- Le moteur dynamique compare maintenant le coût marginal de l'autoconsommation au coût d'opportunité de la réinjection; une contribution solaire partielle peut rendre une charge pertinente sans exiger 100 % de couverture solaire.
- L'Accounting sépare désormais **coût d'achat**, **revenu de réinjection** et **coût de réinjection**. Le coût net suit : `achat + coût export - revenu export`.
- Les prix d'achat négatifs restent signés dans l'Accounting au lieu d'être écrasés à zéro.
- Le libellé utilisateur officiel est **Injection tarifée** ; la compatibilité des anciennes configurations est migrée silencieusement.
- Le dashboard officiel utilise la **même courbe tarifaire normalisée que le backend** : Luminus Dynamic en Dynamique, ComfyFlex en HP/HC. Le graphique interactif, le point « Maintenant » et les décisions économiques lisent la même source FoxCat.
- Une copie harmonisée `homefoxcat_dashboard_client_1.6.158.yaml` est fournie : ses anciens accès directs ComfyFlex sont remplacés par les prix actifs natifs FoxCat, donc Dynamic et HP/HC suivent automatiquement le régime choisi.

Base de développement : **1.6.157 Dynamic Arbitrage**.

## 1. Présentation

FoxCat Energy est une intégration Home Assistant conçue pour piloter et analyser une installation énergétique résidentielle autour de deux mesures physiques souveraines :

- la **puissance réseau signée** ;
- la **production photovoltaïque**.

FoxCat en déduit notamment la consommation réelle de la maison, le prélèvement réseau, la réinjection, l'autoconsommation, l'autonomie, les bilans journaliers et les coûts.

Le système est organisé autour de deux cœurs opérationnels indépendants :

- **EMS Core** : décisions énergétiques, Boiler, machines et protections ;
- **Onduleur Core** : stratégie PRI/RRCR et régulation de l'onduleur.

**Energy Bus** transporte les échanges opérationnels et les ACK/NOK. Le comparateur économique et l'IA prédictive restent séparés du bus de commande.

---

## 2. Ordre fonctionnel officiel

L'ordre des dix sections principales est volontairement stable :

1. Sources énergétiques
2. Énergie
3. Onduleur
4. EMS
5. Energy Bus
6. Machines
7. Boiler
8. Tarification
9. Métronome
10. Diagnostic

Des sous-menus spécialisés peuvent exister, notamment **IA** sous EMS et **Machine Learning** sous Machines, sans modifier cet ordre officiel.

---

## 3. Configuration professionnelle

Le menu **Configurer** est organisé par fonction et entièrement présenté en français.

### EMS

Le menu EMS contient :

- **EMS • Fonctionnement et réglages** ;
- **IA • Prévisions et analyse** ;
- **Retour au menu principal**.

L'ancien libellé « EMS 2 solaire » est remplacé dans l'interface par **IA**. Le module reste consultatif et ne commande directement aucun équipement.

### Machines

Le menu Machines contient :

- Ajouter une machine ;
- Modifier une machine ;
- Supprimer une machine ;
- **Machine Learning** ;
- Retour au menu principal.

Les capteurs issus de l'apprentissage passif sont classés dans le périphérique Home Assistant **FoxCat Energy – Machine Learning** et ne sont plus mélangés avec les capteurs opérationnels Machines.

### Tarification

Le menu Tarification sépare :

- **Tarification dynamique** ;
- **Tarification HP/HC** ;
- Retour au menu principal.

Les recommandations économiques restent hors Energy Bus.

---

## 4. Boiler — sécurité Résistance

La configuration Boiler distingue maintenant deux températures :

- **Température de référence du Boiler** : utilisée pour la régulation ECS normale ;
- **Température Résistance / sécurité** : sonde de sécurité prioritaire lorsqu'elle est configurée.

Le seuil de sécurité reste réglable avec l'entité FoxCat correspondante et vaut **68 °C par défaut**.

Lorsque la température de sécurité atteint ou dépasse ce seuil :

- FoxCat expose la sécurité thermique en défaut ;
- tout nouveau démarrage du Boiler est interdit ;
- un Boiler en chauffe reçoit une demande d'arrêt ;
- la sécurité reste prioritaire sur les modes EMS et les commandes utilisateur.

Si aucune sonde Résistance valide n'est configurée, FoxCat conserve la température de référence historique comme secours de sécurité afin de préserver la compatibilité des installations existantes.

Rôles de registre utiles :

- `boiler.temperature`
- `boiler.resistance_temperature`
- `boiler.resistance_temperature_source`
- `boiler.safety`
- `boiler.safety_source`

---

## 5. Onduleur — puissance physique live

La configuration Onduleur accepte maintenant un **capteur de puissance réelle onduleur en direct**.

Cette mesure ne devient pas une nouvelle horloge EMS :

- le **réseau signé reste la source souveraine des trames** ;
- EMS Core et Onduleur Core continuent à traiter le même snapshot réseau ;
- la puissance onduleur est simplement lue comme contexte physique au moment du snapshot.

Pour le dashboard, le registre expose directement le capteur physique configuré :

- `inverter.power_live` : valeur réellement live du capteur Home Assistant ;
- `inverter.power_snapshot` : valeur mémorisée dans le dernier snapshot FoxCat.

Cette séparation permet un affichage à la seconde sans transformer le capteur onduleur en déclencheur de décisions.

---

## 6. IA prédictive

Le périphérique **FoxCat Energy – IA** regroupe les entités de prévision et de conseil solaire :

- confiance solaire ;
- potentiel solaire ;
- tendance ;
- début et fin de fenêtre solaire ;
- raison de la prévision ;
- fenêtre solaire exploitable ;
- paramètres de prévision ;
- activation de l'analyse prédictive IA.

L'IA peut utiliser Forecast.Solar et un `AI Task` Home Assistant lorsqu'il est configuré. Un fallback déterministe local reste disponible.

**L'IA reste consultative. L'EMS FoxCat reste décisionnaire.**

---

## 7. Machine Learning

FoxCat observe passivement les machines disposant de mesures électriques.

Les données possibles sont :

- puissance ;
- courant ;
- tension ;
- état ON/OFF ;
- début et fin de cycle ;
- durée ;
- énergie du cycle ;
- origine du cycle ;
- contexte PV/réseau/maison ;
- période tarifaire.

Jusqu'à **30 cycles récents par machine** sont conservés localement. Les synthèses exposées comprennent notamment le nombre de cycles, l'état de collecte, la durée moyenne et l'énergie moyenne.

Cette collecte est **strictement passive** dans la branche actuelle et ne modifie pas les décisions EMS/PRI.

---


## 8. Notification persistante EMS

FoxCat peut maintenant maintenir une **notification persistante unique** dans Home Assistant. Elle est mise à jour sous le même identifiant et ne crée donc pas une nouvelle notification à chaque trame.

Le résumé contient :

- le **mode EMS** actif ;
- la **politique réseau** : Compensation ou Injection tarifée ;
- l'**état financier EMS** ;
- la décision économique courante ;
- le régime et la période tarifaire ;
- le prix d'achat actuel ;
- la valeur de réinjection ;
- le coût net réseau du jour.

Le switch **Résumé EMS persistant** permet de désactiver cette fonction. Lorsqu'il est coupé, FoxCat supprime immédiatement sa notification persistante.

L'état financier est également exposé comme capteur afin d'être réutilisable dans le dashboard :

- `pricing.financial_status` ;
- `pricing.financial_detail` ;
- `ems.persistent_status_notification`.

Cette fonction est purement informative : elle ne modifie ni EMS Core, ni Onduleur Core, ni Energy Bus, ni les décisions économiques.

---

## 9. Registre FoxCat

Le dashboard et les composants doivent utiliser des rôles sémantiques plutôt que des `entity_id` FoxCat écrits en dur.

Exemples :

```text
energy.pv_power
energy.house_power
inverter.level_current
inverter.power_live
boiler.temperature
boiler.resistance_temperature
ems.mode
pricing.economic_decision
```

Les entités natives sont résolues par leur `unique_id` Home Assistant. Les sources physiques proviennent de la configuration de l'intégration.

---

## 10. Installation

### HACS / dépôt personnalisé

Copier le dossier :

```text
custom_components/foxcat_energy
```

dans :

```text
/config/custom_components/foxcat_energy
```

puis redémarrer Home Assistant.

Ajouter ensuite l'intégration depuis :

**Paramètres → Appareils et services → Ajouter une intégration → FoxCat Energy**

Après une mise à jour importante, ouvrir **Configurer** et vérifier les nouvelles sources optionnelles avant de régénérer le dashboard.

---

## 11. Principes de sécurité et de stabilité

- La puissance réseau signée reste souveraine pour le cadencement des cœurs.
- Une mesure PV, Boiler ou Onduleur plus rapide ne devient pas automatiquement une seconde horloge.
- Un cycle machine protégé ne doit pas être interrompu par l'optimisation économique.
- La sécurité thermique Boiler est prioritaire sur les stratégies et commandes utilisateur.
- Le comparateur économique ne publie pas de recommandations sur Energy Bus.
- Les changements de version doivent être accompagnés d'un audit anti-régression des fonctions Python.

---

# Historique des versions

## 1.6.157 — Arbitrage dynamique Day-Ahead & modèle thermique Boiler

- Modèle thermique Boiler : énergie manquante et durée estimée.
- Indice Day-Ahead relatif BAS / MEDIAN / HAUT.
- Réservation du meilleur bloc horaire Boiler.
- Première intégration du prix d'export signé dans le PRI.
- Kill-switches prédictif prix et arbitrage solaire.
- Sécurités Boiler et cycles machines préservés.

## 1.6.156 — Résumé EMS persistant et état financier

- Ajout d'une **notification persistante FoxCat unique**, remplacée en place au lieu de créer du spam.
- Affichage du mode EMS, de la politique réseau, de l'état financier, de la décision économique, du tarif courant, de la valeur de réinjection et du coût net du jour.
- Ajout du switch **Résumé EMS persistant** pour activer/désactiver cette fonction.
- Ajout des capteurs **État financier EMS** et **Détail financier EMS**.
- Ajout des rôles de registre `pricing.financial_status`, `pricing.financial_detail` et `ems.persistent_status_notification`.
- Fonction purement informative : aucun changement du PRI, d'InverterCore, d'Energy Bus, du Machine Learning ou de l'algorithme économique.
- Audit anti-régression : **337 → 342 fonctions/méthodes, 5 ajoutées, 0 supprimée**.

## 1.6.155 — Fin solaire sans bascule automatique en ECS solaire

- Suppression du passage automatique du mode **Économie énergie** ou **Zéro injection** vers **ECS solaire** en fin de production PV.
- La détection de fin solaire reste active : FoxCat peut toujours confirmer la fin solaire et libérer l’onduleur à **100 %**.
- Le mode EMS en cours est désormais conservé. **Économie énergie reste Économie énergie** et **Zéro injection reste Zéro injection**.
- Le mode **ECS solaire** reste disponible comme mode explicite, sélectionné par l’utilisateur ou par une future logique spécifiquement autorisée.
- Aucun changement de l’algorithme PRI, de l’InverterCore, de l’Energy Bus, du Machine Learning ou du comparateur économique.
- Audit anti-régression : **337 → 337 fonctions/méthodes, 0 ajoutée, 0 supprimée**.

## 1.6.154 — Configuration professionnelle, IA, Machine Learning et nouvelles mesures

- Refonte de la configuration avec menus et sous-menus plus cohérents.
- Interface de configuration et descriptions enrichies en français.
- Ajout de retours explicites vers le niveau précédent dans les sous-menus EMS, Machines et Tarification.
- « EMS 2 solaire » devient **IA** dans l'interface utilisateur.
- Création du périphérique **FoxCat Energy – IA** pour les entités prédictives.
- Création du périphérique **FoxCat Energy – Machine Learning** pour les capteurs d'apprentissage passif.
- Ajout de la sonde **Température Résistance / sécurité** dans la configuration Boiler.
- La sécurité Résistance utilise le seuil Boiler existant, **68 °C par défaut**.
- Ajout du **capteur de puissance réelle onduleur live** dans la configuration Onduleur.
- Nouveau rôle `inverter.power_live` pour permettre au dashboard d'utiliser directement la mesure physique rapide.
- Nouveau snapshot `inverter.power_snapshot`, sans changement du cadencement EMS/PRI.
- Registre enrichi avec les rôles Boiler sécurité et Machine Learning.
- Documentation consolidée dans ce README unique pour l'installation, l'architecture fonctionnelle et l'historique des versions.
- Base : 1.6.153 originale, sans reprise des prototypes Premium UI abandonnés.
- Audit anti-régression : **331 → 337 fonctions/méthodes, 6 ajoutées, 0 supprimée**.

## 1.6.153 — Comparateur économique HP/HC & dynamique

- Comparateur économique local séparé d'Energy Bus.
- Comparaison des créneaux HP/HC et dynamiques actuels/futurs.
- Prise en compte du coût d'opportunité du solaire et de la valeur de réinjection.
- Utilisation des profils machines pour estimer durée et énergie d'un cycle.
- Capteur **Décision économique EMS** et recommandations par machine.
- Compensation : onduleur 100 % direct.
- Injection tarifée : moteur PRI prédictif conservé.
- Audit : **309 → 331 fonctions/méthodes, 0 suppression**.

## 1.6.152 — Collecte passive machines et accounting natif

- Collecte locale des signatures électriques des machines.
- Capteurs courant/tension optionnels par machine.
- Contexte machine enrichi sans influence sur EMS/PRI.
- Correction du conflit `origin` Energy Bus.
- KPI journaliers du dashboard migrés vers l'accounting natif FoxCat.
- Tarifs affichés selon le régime actif.

## 1.6.151 — Correctif PRI et commandes utilisateur

- Correction de `_classify_pri_grid` manquant.
- Commandes utilisateur démarrage/arrêt pour les machines.
- Boiler : FORCE_ON, FORCE_OFF et retour AUTO.
- Protection des cycles lancés par l'utilisateur.

## 1.6.150 — Cadencement réseau souverain

- Chaque publication réelle du réseau crée une trame commune aux deux cœurs.
- Le Métronome devient watchdog/fallback et non horloge périodique de décision.
- EMS Core et Onduleur Core utilisent le même snapshot et le même numéro de trame.
- Workers physiques séparés pour RRCR et Boiler afin de ne pas bloquer les nouvelles acquisitions.
- ACK/NOK Energy Bus renforcés.
- Import excessif autorisant la remontée immédiate du PRI.

## 1.6.1-101 — Compteurs journaliers sûrs

- Reset quotidien des compteurs visibles.
- Séquences techniques internes séparées des compteurs journaliers.
- Messages non acquittés clôturés en TIMEOUT à la fin de journée.

## 1.6.1 — Machine à états et Energy Bus renforcé

- États EMS explicites Acquisition → Décision → Attente ACK.
- Diagnostics de transitions et gestion plus formelle des ACK/NOK.

## 1.6.0 — Modèle énergétique unifié et registre

- Deux sources physiques principales : réseau signé + PV.
- Calcul interne maison/import/export.
- Ordre officiel des dix sections.
- Registre sémantique des entités et génération dashboard basée sur rôles.
- PRI reste un nom interne ; l'utilisateur voit **Onduleur**.

## 1.5.5 — PRI prédictif

- Simulation directe des niveaux RRCR par pas de 10 %.
- Calcul de la charge maison et du meilleur palier cible.
- Commande directe du niveau optimal au lieu d'une descente lente palier par palier.

## 1.5.4 — Métronome réseau

- Source réseau configurable et fallback.
- Détection des republications identiques lorsque Home Assistant le permet.
- Diagnostics de fraîcheur et de cadence.

## 1.5.3 — Reprise PRI automatique

- Filet de sécurité contre un blocage après une première variation de palier.

## 1.5.2 — Protection native des cycles machines

- `MachineCycleManager`.
- Détection de démarrage, durée théorique, fin confirmée et timeout.
- Les pauses temporaires à 0 W ne terminent plus prématurément un cycle.

## 1.5.1 — Stabilisation

- Source réseau souveraine unique pour l'Onduleur Core.
- Corrections de télémétrie et de diagnostics.

## 1.5.0 — Architecture double cœur

- EMS Core ↔ Energy Bus ↔ Onduleur Core.
- Politiques Compensation / Injection tarifée.
- Premiers comparateurs PV/plafond et comptabilité HP/HC par appareil.

---

## Licence

Voir `Licence.md.txt`.
