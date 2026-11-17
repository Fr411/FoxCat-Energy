# Manuel de configuration FoxCat Energy

Ce manuel vous guide **pas à pas**, de l'installation à la mise en route de la régulation. Pour comprendre comment FoxCat fonctionne, lisez le [README](readme.md).

**Durée prévue** : 30 à 60 minutes pour l'installation, puis quelques jours d'observation avant de tout automatiser.

---

## Sommaire

1. [Avant de commencer](#1-avant-de-commencer)
2. [Installer l'intégration](#2-installer-lintégration)
3. [Assistant d'installation](#3-assistant-dinstallation)
4. [Premier contrôle, régulation à l'arrêt](#4-premier-contrôle-régulation-à-larrêt)
5. [Le menu de configuration](#5-le-menu-de-configuration)
6. [Régler la tarification](#6-régler-la-tarification)
7. [Configurer les équipements](#7-configurer-les-équipements)
8. [Protéger le raccordement](#8-protéger-le-raccordement)
9. [Prévisions et IA](#9-prévisions-et-ia)
10. [Activer la régulation, étape par étape](#10-activer-la-régulation-étape-par-étape)
11. [Installer les dashboards](#11-installer-les-dashboards)
12. [Profils de réglages](#12-profils-de-réglages)
13. [Dépannage](#13-dépannage)
14. [Retour arrière](#14-retour-arrière)

---

## 1. Avant de commencer

### Matériel et accès

- Home Assistant **2025.1.0 ou plus récent**.
- Un capteur de **puissance réseau signée** (W) au point de raccordement : un seul capteur qui est positif au prélèvement et négatif à la réinjection (ou l'inverse).
- Un capteur de **production photovoltaïque** instantanée (W).
- Selon ce que vous voulez piloter : le thermostat du boiler, les prises des machines, les quatre relais RRCR de l'onduleur.

### Ce qu'il faut savoir sur votre contrat

Notez ces informations avant de lancer l'assistant :

| Question | Où la trouver |
|---|---|
| Contrat fixe, variable ou dynamique ? | Votre contrat ou votre facture |
| Tarif réseau : mono-horaire, bi-horaire ou « Impact » ? | Facture, rubrique distribution |
| Prix du kWh (HP et HC si bi-horaire), prix de réinjection | Facture ou fiche tarifaire |
| Vos prix incluent-ils réseau, taxes et marge (« tout compris ») ? | Fiche tarifaire |
| Région (Wallonie, Flandre, Bruxelles) | Votre adresse |
| Terme capacitaire et redevance prosumer | Facture du gestionnaire de réseau |
| Calibre du disjoncteur (A) et nombre de phases | Tableau électrique |

### Précautions

- **Désactivez** les automatisations existantes qui commandent les mêmes équipements, sinon les commandes se contrarient.
- Prévoyez de laisser la régulation à **l'arrêt** lors du premier contrôle (étape 4).
- Vous pouvez tout modifier plus tard : rien n'est définitif.

---

## 2. Installer l'intégration

### Avec HACS (recommandé)

1. Dans HACS, ouvrez **Intégrations**, puis le menu **⋮ → Dépôts personnalisés**.
2. Ajoutez `https://github.com/Fr411/FoxCat-Energy` avec la catégorie **Intégration**.
3. Cherchez **FoxCat Energy**, installez-le.
4. **Redémarrez Home Assistant** complètement.

### À la main

1. Copiez le dossier `custom_components/foxcat_energy` dans `/config/custom_components/foxcat_energy`.
2. Redémarrez Home Assistant.

### Mise à jour depuis une version précédente

Mettez à jour via HACS, redémarrez, puis ouvrez **Paramètres → Appareils et services → FoxCat Energy → Configurer** et passez en revue **Tarification**. Vos `entity_id` sont conservés. Une installation existante garde son comportement : les nouveautés (prix tout compris, coûts réseau…) sont à activer volontairement.

---

## 3. Assistant d'installation

**Paramètres → Appareils et services → Ajouter une intégration → FoxCat Energy.**

L'assistant se déroule dans cet ordre : **Contrat → Réseau → Prix → Sources → Boiler → Onduleur → Machines → (Tarification dynamique) → IA**. Chaque étape peut être laissée vide quand elle est facultative.

### Étape 1/3 : Contrat

| Champ | Choix |
|---|---|
| **Type de contrat** | *Prix fixe ou variable* (vous saisissez vos prix ou lisez des capteurs) ou *Dynamique* (prix horaire ou au quart d'heure) |
| **Région** | Wallonie, Flandre, Bruxelles ou Autre |

La région sert uniquement à préselectionner les tarifs du comparateur. **Elle ne modifie aucun prix.**

### Étape 2/3 : Réseau

| Champ | Choix |
|---|---|
| **Structure du tarif de réseau** | *Mono-horaire* (un prix), *Bi-horaire* (heures pleines / creuses) ou *Impact* (ECO / MEDIUM / PIC) |
| **Mes prix sont « tout compris »** | À cocher si le prix saisi ou lu contient déjà le réseau, les taxes et la marge du fournisseur |

> **Cochez « tout compris » dans le doute ?** Non : cochez-la seulement si c'est vrai. Si votre prix est un prix d'énergie nu et que vous cochez la case, FoxCat n'ajoutera pas les coûts de distribution et sous-estimera vos coûts. Inversement, si votre prix est déjà tout compris et que la case est décochée, FoxCat les comptera deux fois. Un prix lu depuis une intégration « tout compris » (par exemple le champ `all_in` de Luminus Dynamic) se coche.

La structure du réseau est **indépendante** du contrat : on peut avoir un contrat fixe avec un réseau bi-horaire, ou un contrat dynamique avec un réseau Impact.

### Étape 3/3 : Vos prix

*(Cette étape est sautée pour un contrat dynamique.)*

1. **Source des prix** : *Je saisis mes prix* ou *Je lis mes prix depuis des capteurs*.
2. Selon la structure choisie :

| Structure | Saisie manuelle | Capteurs |
|---|---|---|
| Mono-horaire ou Impact | Prix d'achat (€/kWh), prix de réinjection (facultatif) | Capteur du prix d'achat, capteur de réinjection (facultatif) |
| Bi-horaire | Prix HP, prix HC, prix de réinjection (facultatif) | Capteur HP, capteur HC, capteur de réinjection (facultatif) |

Le **prix de réinjection** est facultatif : laissez-le vide s'il n'est pas valorisé.

### Sources énergétiques

| Champ | Explication |
|---|---|
| **Nom de l'installation** | Nom visible, par exemple « Maison » |
| **Puissance réseau signée** | Votre capteur de puissance au compteur (W) |
| **Convention du signe réseau** | *+ prélèvement / − réinjection*, ou l'inverse. **Vérifiez-la** : tirez de l'électricité depuis le réseau (allumez une bouilloire) et regardez si la valeur monte |
| **Production photovoltaïque** | Votre capteur de production (W) |

Sections facultatives :

- **Protection du raccordement** : activer le délestage, calibre du disjoncteur (A), tension nominale. Laissez à 0 pour renseigner plus tard (voir [§ 8](#8-protéger-le-raccordement)).
- **Avancé** : puissance réseau de secours (utilisée seulement si la source principale se fige) et **mode développeur** (laissez désactivé).

### Boiler

*Facultatif : laissez vide si vous n'avez pas de chauffe-eau à piloter.*

| Champ | Explication |
|---|---|
| **Thermostat du boiler** | L'entité `climate` que FoxCat commande |
| **Température de référence** | Sonde d'eau du boiler |
| **Puissance du boiler** | Capteur de puissance (confirme l'état physique, alimente la comptabilité) |
| **État physique** | Capteur binaire marche/arrêt, référence de cycle |
| **Température résistance / sécurité** | Sonde au plus près de la résistance. Au-dessus de **68 °C**, toute chauffe est interdite |
| **Modèle thermique** | Volume (L), puissance de la résistance (W), température d'eau froide (15 °C par défaut). Servent uniquement à l'arbitrage en tarification dynamique |

### Onduleur

*Facultatif : seulement si votre onduleur se pilote par RRCR.*

- **Relais PRI L1 à L4** : les quatre entrées de commande RRCR, dans l'ordre des bits.
- **Puissance réelle de l'onduleur en direct** (facultatif) : télémétrie rapide, purement informative.

### Machines

Déclarez ici le **lave-linge**, le **sèche-linge** et le **lave-vaisselle** (prise de commande, capteur de puissance, plages). Vous pourrez en ajouter d'autres, et régler les cycles, plus tard dans le menu **Équipements → Machines**.

### Tarification dynamique

*(Uniquement pour un contrat dynamique.)* Indiquez les entités de votre fournisseur de prix :

| Champ | Explication |
|---|---|
| **Prix actuel** | Prix d'achat « tout compris » du quart d'heure ou de l'heure en cours |
| **Prix heure suivante** | Prix de la période suivante |
| **Prix de réinjection** | Valeur de la réinjection |
| **Convention de signe réinjection** | Positif = rémunérateur |

Sections : **statistiques journalières** (minimum, maximum, moyenne d'aujourd'hui et de demain), **séries de prix futurs** (courbes du jour et du lendemain), **stratégie**.

### IA

Facultatif : un **agent IA** (AI Task) de Home Assistant et vos capteurs de **prévision solaire** (Forecast.Solar). Sans IA, FoxCat garde un fonctionnement déterministe.

À la fin, l'intégration est créée. **La régulation n'est pas encore active.**

---

## 4. Premier contrôle, régulation à l'arrêt

Avant de laisser FoxCat commander quoi que ce soit :

1. Ouvrez **Paramètres → Appareils et services → FoxCat Energy**. Vous voyez **10 appareils** : Mesures et sources, Tarification, Onduleur, Boiler, Chauffage, Machines, Batterie et VE, Protection, Prévisions et IA, Système.
2. Vérifiez que l'interrupteur **« Régulation FoxCat active »** est sur **OFF**.
3. Dans l'appareil **Mesures et sources**, comparez les valeurs avec votre compteur :
   - la consommation de la maison est cohérente ;
   - le prélèvement monte quand vous consommez, la réinjection monte quand le soleil dépasse la consommation. Si c'est inversé, corrigez la **convention de signe**.
4. Dans **Tarification**, vérifiez que le **prix d'achat actif**, la **période** (HP/HC) et le **statut du prix** correspondent à votre contrat.
5. Dans **Système**, regardez les capteurs de diagnostic : aucune erreur persistante.
6. Laissez tourner **quelques heures à quelques jours**. Le comparateur de tarifs a besoin de quelques heures de mesure pour afficher des chiffres.

---

## 5. Le menu de configuration

**Paramètres → Appareils et services → FoxCat Energy → Configurer.**

| Entrée | Contenu |
|---|---|
| **Mesures et sources** | Puissance réseau, production PV, convention de signe, source de secours |
| **Tarification** | Contrat et réseau, entités de prix dynamiques, prix HP/HC, coûts réseau et prosumer, publication des prix, comparateur |
| **Équipements** | Onduleur, Boiler, Chauffage, Machines, Batterie et VE |
| **Protection** | Délestage et protection du raccordement |
| **Prévisions et IA** | Prévisions solaires et agent IA |
| **À propos du fonctionnement** | Rappel des briques (énergie, EMS, bus, métronome, diagnostic, apprentissage) |
| **✓ Enregistrer et quitter** | Applique et enregistre |

> **Important** : les modifications restent **en mémoire** tant que vous n'avez pas choisi **« Enregistrer et quitter »**. Fermer la fenêtre avant les annule. Un avertissement s'affiche en tête de menu tant que des changements ne sont pas enregistrés.

Chaque sous-menu propose un retour au menu principal. Vider un champ d'entité est bien enregistré.

---

## 6. Régler la tarification

**Configurer → Tarification.**

### 6.1 Contrat et réseau

L'écran **Contrat et réseau** écrit ensemble la source, la structure, le régime et le profil de distribution, pour qu'ils restent cohérents.

1. **Source des prix** : *Contractuelle / fixe*, *Variable via entités Home Assistant*, *Intégration externe* ou *Dynamique Day-Ahead*.
2. **Structure du tarif de réseau** : mono-horaire, bi-horaire ou Impact.
3. **Mes prix sont « tout compris »** : voir l'avertissement de l'[étape 2/3](#étape-23--réseau).
4. **Réinjection** (politique réseau) :
   - *Compensation* : la réinjection compense le prélèvement ;
   - *Injection tarifée* : vendue au prix de réinjection ;
   - *Injection non valorisée* : ne rapporte rien, FoxCat cherche à l'éviter ;
   - *Zéro injection* : FoxCat vise une injection nulle.
5. Prix saisis, **seulement avec « Prix saisis à la main »** : prix d'achat unique (mono et Impact), prix HP et HC (bi-horaire), prix de réinjection.

**Les listes de Home Assistant suivent le menu.** Dans l'appareil **Tarification**, les listes « Source du prix », « Structure tarifaire », « Régime Tarifaire », « Profil distribution Belgique » et « Structure (Si Dynamique) » modifient les mêmes deux choix que cet écran (contrat et structure du réseau) et mettent à jour toutes les autres clés. Vous pouvez donc changer de tarif d'un côté ou de l'autre : le résultat est identique, et le menu reflète toujours l'état des listes.

- « Source du prix » : Contractuelle / fixe, Variable via entités Home Assistant, Dynamique Day-Ahead.
- « Structure tarifaire » : Simple, Bi-horaire ou Impact, avec tous les contrats.
- « Régime Tarifaire » : *Mono-horaire* et *Bi-horaire (HP/HC)* passent le contrat en non dynamique ; *Mono-horaire* remet la structure à Simple (pour Impact, utilisez « Structure tarifaire »).

> **Si vous aviez une automatisation** qui sélectionnait « Bihoraire » ou « Dynamique » dans « Source du prix » : ces choix n'existent plus. Utilisez « Régime Tarifaire » (Bi-horaire (HP/HC) ou Dynamique).

### 6.2 Prix et plages HP/HC

Pour un tarif bi-horaire : prix d'achat et de réinjection, et **plages** des heures creuses. Le tarif actif se choisit ensuite avec le sélecteur **« Régime tarifaire »** de FoxCat ; ces réglages peuvent être préparés à l'avance.

### 6.3 Entités de prix dynamiques

Les entités de prix actuel, prix suivant, réinjection et séries, comme dans l'assistant. Réglages de stratégie utiles :

| Réglage | Effet | Défaut |
|---|---|---|
| Position « favorable » | Un prix est favorable s'il est dans les x % les plus bas de l'horizon | 30 % |
| Durée favorable maximale | Nombre d'heures favorables retenues | 4 h |
| Charge réseau si prix négatif | Autorise le boiler à charger quand le prix est négatif | Activé |

### 6.4 Coûts réseau et prosumer

Ces coûts dépendent de **votre gestionnaire de réseau**, pas de votre fournisseur. Reprenez les montants de votre facture ; à l'installation, la Flandre et Bruxelles proposent des moyennes du guide des tarifs à remplacer.

| Champ | Utilisation |
|---|---|
| **Terme capacitaire** | *Aucun*, *Forfait annuel* (Bruxelles) ou *Pointe mensuelle* (Flandre) |
| Forfait capacitaire annuel | Avec « Forfait annuel » |
| Prix par kW de pointe | Avec « Pointe mensuelle » (montant annuel par kW). La pointe facturée est la **moyenne des pointes mensuelles** (12 mois au plus) ; FoxCat la mémorise et la reconstitue au démarrage |
| Puissance minimale facturée | Avec « Pointe mensuelle » : 2,5 kW en Flandre, appliqués à **chaque mois** avant la moyenne |
| **Redevance prosumer annuelle** | Redevance pour les panneaux solaires, ramenée à l'année |
| Contrôles (facultatifs) | Entités de l'intégration de prix : coût capacitaire, pointe mensuelle, coût prosumer. Elles servent de **vérification** et ne s'additionnent pas |

Résultat : le capteur **« Coûts réseau • Ce mois »**.

### 6.5 Publication des prix

Pour que FoxCat relise les prix dès que ceux du lendemain sont publiés :

1. **Entité de publication** : un capteur binaire (déclenche en passant à *on*) ou un capteur d'horodatage (déclenche à chaque changement), par exemple « prix de demain disponible » de Nord Pool.
2. **Service de relecture** (facultatif) : au format `domaine.service`, par exemple `be_electricity_prices.refresh`. Appelé au plus **une fois toutes les 10 minutes**.

### 6.5 bis Coupure Internet : rien à configurer

Avec une source de prix **Dynamique Day-Ahead** ou **Intégration externe**, FoxCat garde automatiquement en mémoire les prix reçus. Aucun réglage n'est nécessaire.

1. Ouvrez le capteur **« Flux de prix (en ligne / tampon local) »** de l'appareil Tarification.
2. Lisez son état : `EN_LIGNE` (tout va bien), `TAMPON` (Internet coupé, FoxCat continue avec les prix mémorisés jusqu'à `buffer_until`), `DEGRADE` (tampon épuisé), `LOCAL` (contrat fixe : aucune connexion nécessaire).
3. En `DEGRADE`, le boiler dynamique chauffe seulement jusqu'à 45 °C sur le réseau, sans BOOST réseau. Les machines différées attendent le retour des prix.
4. Pour tester : coupez l'entité de prix (désactivez-la) un court instant et vérifiez le passage à `TAMPON`. Réactivez-la : l'état revient à `EN_LIGNE`.

La prévision solaire en ligne et la tâche IA ne fonctionnent pas hors ligne. La comptabilité compte 0 € d'achat tant qu'aucun prix n'existe.

### 6.5 ter Mode Backup (Internet coupé)

Le mode Backup est actif par défaut.

1. Ouvrez l'appareil **Système** : les capteurs **« Internet en ligne »** et **« Mode Backup actif »** y sont créés.
2. Réglez la durée de coupure avant déclenchement (**« Backup : durée de coupure avant déclenchement »**, 2 minutes par défaut) : une micro-coupure plus courte ne déclenche rien.
3. Pour désactiver le mode : coupez **« Mode Backup si Internet coupé »**.
4. Pour tester : débranchez le routeur plus longtemps que la durée réglée. Vérifiez que « Internet en ligne » passe à *hors ligne*, que les prises machines restent alimentées et que le boiler est coupé. Rebranchez : au bout d'environ une minute, les prises reprennent leur état d'avant la coupure.
5. L'attribut `prises_memorisees` du capteur « Mode Backup actif » montre l'état enregistré.

En Backup, le **boiler est coupé** : l'eau chaude n'est plus chauffée tant qu'Internet est absent. Reste actif : le délestage du disjoncteur. En mode **Manuel**, ou si la régulation est coupée, FoxCat ne commande rien : seul le capteur signale la coupure.

### 6.5 quater Alertes de panne

Les alertes sont actives par défaut, sans réglage.

1. Dans l'appareil **Système**, le capteur **« Santé FoxCat (alertes de panne) »** vaut `OK`, `MAJEUR` ou `CRITIQUE`. Ses attributs listent chaque alerte avec sa cause et l'heure de début.
2. Home Assistant affiche une notification (cloche) par alerte, retirée quand la panne est levée.
3. Pour recevoir un message sur le téléphone : importez `docs/automations/alerte_panne_foxcat.yaml` dans Paramètres → Automatisations, et remplacez `notify.mobile_app_mon_telephone` par votre service de notification.
4. Pour couper les notifications : interrupteur **« Alertes de panne FoxCat (notifications) »**. Les capteurs restent.
5. Test : désactivez le capteur de puissance réseau pendant plus de 2 minutes : l'alerte **« FoxCat ne reçoit plus les mesures »** apparaît, puis disparaît une minute après le retour du capteur.

Une alerte ne signale qu'une panne (capteur, commande, connexion). Un mauvais réglage ou un mauvais choix économique ne déclenche rien.

### 6.6 Comparateur de tarifs

1. **Modèles** : ajoutez des modèles belges prédéfinis (Wallonie mono, bi-horaire 2026, Impact). Un modèle ajoute un tarif avec des **prix de départ** : modifiez-les ensuite dans le JSON.
2. **Tarifs (JSON)** : liste de tarifs, modifiable et copiable d'une installation à l'autre. Un tarif présent ici l'emporte sur le modèle du même identifiant. Les identifiants **`active`** et **`contract`** sont réservés.

Les tarifs « actuel » et « contrat saisi » sont ajoutés automatiquement. Vous obtenez les capteurs **« Comparateur de tarifs • Aujourd'hui »** et **« • Ce mois »**.

> Le comparateur compare **à comportement constant** : il rejoue la consommation mesurée sur chaque tarif, sans rejouer le pilotage de FoxCat.

---

## 7. Configurer les équipements

**Configurer → Équipements.**

### 7.1 Boiler

Mêmes champs que dans l'assistant, plus les réglages de comportement dans les entités de l'appareil **Boiler** :

| Entité | Rôle | Défaut |
|---|---|---|
| Boiler géré par FoxCat | Interrupteur général du pilotage | — |
| Boiler autorisé en heures creuses | Autorise la chauffe réseau en HC | — |
| Boiler : attendre le dernier failback en HC | Laisse la priorité au solaire avant de chauffer sur le réseau | Activé |
| Marge de sécurité failback | Marge avant l'échéance | 30 min |
| Température reprise / confort / boost / sécurité | Seuils de chauffe | 43 / 45 / 65 / 68 °C |
| Cycle minimum | Durée mini d'un cycle | 120 s |
| Puissance chauffe-eau | Puissance nominale | 1 800 W |
| Agressivité solaire Bihoraire | **Inactif** : sans effet dans cette version | — |

**Conseils** : placez la sonde de sécurité au plus près de la résistance ; ne montez jamais le seuil de sécurité au-dessus de ce que supporte votre chauffe-eau.

### 7.2 Onduleur (PRI / RRCR)

1. Renseignez les **quatre relais** L1 à L4 dans le bon ordre.
2. Ajoutez, si vous l'avez, le **capteur de puissance live**.
3. Activez **« Réduction de puissance onduleur »** seulement après vérification (étape 10).

Le bouton **« Libérer l'onduleur à 100 % »** annule toute réduction : c'est votre retour arrière immédiat.

### 7.3 Machines

Menu **Machines** : *Ajouter*, *Modifier*, *Supprimer*. Supprimer une machine la retire de FoxCat sans supprimer aucune entité Home Assistant.

**Ajouter une machine :**

| Champ | Explication |
|---|---|
| **Nom de la machine** | Par exemple « Pompe de piscine » |
| **Type de machine** | *Switch pilotable* ou *CVC en télémétrie seule* |
| **Prise / relais de commande** | Le switch qui coupe ou autorise la machine |
| **Capteur de puissance** | Obligatoire pour un CVC ; recommandé sinon (comptabilité et détection de cycle) |

Sections : **Automatisation** (gestion automatique, délestable, phase du réseau L1/L2/L3), **Cycle** (détection et protection du cycle), **Mesures**.

Bon à savoir :

- Une machine **en cycle n'est jamais coupée** en plein programme.
- Seules les machines marquées **délestables** sont coupées pendant un délestage.
- FoxCat apprend passivement jusqu'à **30 cycles** par machine mesurée, sans influencer ses décisions.
- Un CVC (climatisation, PAC) est **observé** et comptabilisé séparément, jamais commandé.

### 7.4 Chauffage

Menu **Chauffage** :

1. **Réglages du décalage de consigne** : activer la fonction (désactivée par défaut), « uniquement maison vide », entité de présence (`zone.home` par défaut), puissance et limite du groupe de climatisation, règles de calcul (décalage maximal 2 °C, pas 0,5 °C, surplus requis par pas, marge de réserve, délai anti-yoyo 300 s, import maximal 300 W).
2. **Systèmes de chauffage** : ajoutez vos pompes à chaleur (groupe extérieur : puissance, tension, phase ; jusqu'à 5 unités intérieures pour une PAC air/air).
3. **Entités créées par FoxCat** : liste l'`entity_id` réel de chaque entité, sans helper à créer.

**Appliquer le décalage** : FoxCat calcule et publie seulement le décalage. Importez l'automatisation d'exemple [`docs/automations/etage_decalage_vtherm.yaml`](docs/automations/etage_decalage_vtherm.yaml), adaptez les `climate.*` de **Versatile Thermostat**, puis activez-la.

### 7.5 Batterie et véhicule électrique

- **Activer la simulation** (désactivée par défaut) et le **mode shadow**. La simulation **ne commande aucun appareil** et reste isolée du registre réel.
- **Batterie virtuelle** : capacité, puissances de charge et décharge, rendements, réserve.
- **Véhicule virtuel** : capacité, puissance de charge, rendement.
- **Coûts d'usure** (€/kWh) pour l'arbitrage virtuel.
- **V2H physique** (fonction distincte, opt-in) : commande V2H du chargeur, consigne de puissance, état de charge réel du véhicule, puissance maximale, **réserve de mobilité minimale**. N'activez le V2H qu'avec une commande explicitement configurée.

---

## 8. Protéger le raccordement

**Configurer → Protection.** Quand la puissance dépasse un seuil, FoxCat **délestera** les charges non essentielles puis les rétablit.

1. **Activer le délestage haute consommation.**
2. **Raccordement** : régime réseau (MONO / TRI / TETRA), **calibre du disjoncteur** (A), tension nominale, facteur de puissance de l'onduleur, nombre de phases prises en compte.
3. **Seuils** :
   - avec disjoncteur renseigné : déclenchement à **90 %** du disjoncteur (réglable) ;
   - sans disjoncteur : seuil absolu en watts ;
   - **puissance comparée** : *Import réseau* (recommandé avec du solaire : évite de délester quand le soleil couvre la charge) ou *Consommation totale* ;
   - **réarmement** : toujours au moins 5 % sous le déclenchement.
4. **Actions pendant le délestage** : couper le boiler, couper les machines délestables, libérer l'onduleur, bloquer les nouveaux démarrages flexibles, V2H (cible 80 % du disjoncteur).
5. **Mesures** (facultatives) : tensions réseau et intensités par phase (voir ci-dessous).

> Exemple : disjoncteur 40 A en monophasé 230 V, soit 9 200 W ; déclenchement à 90 % ≈ 8 280 W.

### Sans capteur d'intensité par phase

C'est le cas si vous n'avez que les tensions (phase-neutre et entre lignes) et une puissance totale. Un disjoncteur déclenche sur la phase la plus chargée : FoxCat ne peut pas la connaître sans courant par phase, mais vous pouvez le rendre plus prudent.

1. **Régime réseau** : *TRI* ou *TETRA*, et **nombre de phases = 3**.
2. **Calibre du disjoncteur** et tension nominale (230 V).
3. Dans **Mesures**, renseignez les capteurs de tension que vous avez : L1, L2, L3 (≈ 230 V) et/ou L1-L2, L2-L3, L3-L1 (≈ 400 V). Un seul groupe suffit : FoxCat déduit l'autre. Laissez vides les intensités L1 à L3.
4. **Coefficient de déséquilibre des phases** : commencez à **1,3**. Il suppose que la phase la plus chargée porte 30 % de plus que la moyenne et abaisse le seuil de délestage d'autant. Exemple : 25 A, 3 phases, 230 V, 90 % → 15 525 W avec K = 1, **11 942 W avec K = 1,3**.
5. **Observez** : ouvrez l'entité **« Charge du disjoncteur principal »** (appareil Protection) et lisez ses attributs : `source_tension` doit valoir `phase`, `line` ou `phase+line` (pas `nominal`), `tension_phase_v` doit être proche de 230 V, et `ecart_tension_phases_pct` donne l'écart entre vos phases.
6. **Ajustez le coefficient** selon vos habitudes. Si un disjoncteur a déjà déclenché alors que le total semblait bas, augmentez-le (1,5 à 2). Si le délestage se déclenche trop tôt, baissez-le. Ne le montez pas en monophasé : il est sans effet.

Les tensions n'indiquent pas quelle phase est la plus chargée : elles rendent le calcul plus juste, mais seul le coefficient couvre un déséquilibre.

---

## 9. Prévisions et IA

**Configurer → Prévisions et IA.**

- Capteurs de **prévision solaire** (Forecast.Solar).
- **Agent IA** (AI Task) : facultatif.
- Interrupteurs : **Analyse prédictive IA**, **Optimisation économique des charges flexibles**, **Prédictif prix dynamique**, **Arbitrage prévision solaire**.

Ces modules sont **consultatifs** : ils conseillent mais ne commandent jamais directement un équipement.

N'oubliez pas **« Enregistrer et quitter »**.

---

## 10. Activer la régulation, étape par étape

Procédez **progressivement**, en observant à chaque étape.

| # | Action | À vérifier |
|---|---|---|
| 1 | Laissez **Régulation FoxCat active = OFF** pendant 24 à 48 h | Mesures, prix et période corrects |
| 2 | Choisissez le **Mode EMS : Manuel** | Rien n'est commandé automatiquement |
| 3 | Choisissez le **contrat et la structure** (liste « Source du prix » et « Structure tarifaire », ou l'écran Contrat et réseau) puis la **Politique réseau** | Le prix actif suit bien votre contrat, et les listes de tarif affichent les mêmes valeurs que le menu |
| 4 | Activez **Régulation FoxCat active** (toujours en Manuel) | Aucune erreur de diagnostic |
| 5 | Passez en **Éco** avec seulement **le boiler** géré (« Boiler géré par FoxCat ») | Le boiler chauffe avec le surplus, jamais en HP |
| 6 | Activez la **gestion de chaque machine**, une à la fois | La machine démarre dans la fenêtre prévue, un cycle n'est jamais coupé |
| 7 | Activez **« Réduction de puissance onduleur »** | La puissance de l'onduleur suit les paliers, pas d'oscillation |
| 8 | Activez le **délestage** et le **décalage de chauffage** si voulus | Le délestage réarme proprement |
| 9 | Activez **Optimisation économique / Prédictif prix** | Les décisions sont cohérentes avec la courbe de prix |

Le mode **Confort** applique la même stratégie boiler et la même réduction de l'onduleur qu'Éco, sécurités conservées (seul le planificateur de charges flexibles se montre moins patient). Le mode **Manuel** suspend le pilotage automatique du boiler, de l'onduleur et des machines (la sécurité thermique reste active) : utile pour reprendre la main.

### Réglages fins

Les seuils du moteur (tolérances ACK, stabilité, watchdog, paliers PRI, import cible, etc.) sont des entités **nombre** dans l'appareil concerné (Onduleur, Système, Tarification). Modifiez-les **un par un** et observez. Gardez les valeurs par défaut tant que tout fonctionne.

> **Entités « inactives »** : certaines entités de réglage n'ont aucun effet dans cette version (agressivité solaire, charge réseau sur prix négatif, plusieurs seuils PRI…). Elles sont créées désactivées, rangées en diagnostic et portent l'attribut `statut: inactif` ; inutile de les régler. Si vous les aviez déjà activées, vous pouvez les désactiver.

---

## 11. Installer les dashboards

### Dashboards générés par FoxCat

FoxCat crée dans `/config/foxcat_energy/` :

- `dashboard.yaml` : tablette / PC ;
- `dashboardmob1.yaml` : mobile.

Les fichiers existants **ne sont jamais écrasés** au démarrage.

1. Fusionnez **une seule fois** le contenu de [`configuration.yaml.snippet`](configuration.yaml.snippet) dans `/config/configuration.yaml` : il déclare les deux dashboards (`foxcat-energy` pour tablette/PC, `foxcat-energy2` pour mobile).
2. Redémarrez Home Assistant.
3. Les dashboards apparaissent dans la barre latérale.

> Ne modifiez **pas** `.storage/lovelace_dashboards` directement.

### Cartes nécessaires

Installez (via HACS, catégorie Interface) : **`button-card`**, **`apexcharts-card`**, **`card-mod`**.

### Choisir et mettre à jour les versions

- Les listes **Version du dashboard tablette/PC** et **Version du dashboard mobile** sont indépendantes.
- Le bouton **Régénérer le dashboard FoxCat** force la régénération, avec une sauvegarde `.bak` avant chaque remplacement.
- La **fusion à trois sources** conserve vos modifications non conflictuelles, signale les conflits et sauvegarde le dashboard courant.

### Vue « Coûts » à jour

Copiez le YAML de la vue dans l'éditeur de votre dashboard :

- tablette : [`docs/cartes/vue_couts.yaml`](docs/cartes/vue_couts.yaml) ;
- mobile : [`docs/mobile/cartes/vue_couts_mobile.yaml`](docs/mobile/cartes/vue_couts_mobile.yaml).

Elle affiche la tarification active, le comparateur, les coûts réseau, les économies FoxCat et les graphiques de prix. Les entités sont retrouvées par leur nom : rien à remplacer.

Si l'image ne s'affiche pas immédiatement, videz le cache de l'application Home Assistant ou rechargez la page.

---

## 12. Profils de réglages

Sauvegardez vos réglages avant d'expérimenter. Dans **Outils de développement → Actions** :

| Action | Effet |
|---|---|
| `foxcat_energy.save_settings_profile` | Enregistre un profil dans `/config/foxcat_energy/profiles/` (nom de 1 à 64 lettres, chiffres, tirets ou soulignés) |
| `foxcat_energy.load_settings_profile` | Valide puis applique un profil |
| `foxcat_energy.reset_settings` | Restaure les valeurs par défaut du moteur et des machines |

---

## 13. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Prélèvement et réinjection inversés | Convention de signe | **Mesures et sources**, inversez la convention |
| Alerte « Sonde de température du boiler indisponible » | La sonde du boiler ne répond plus | Rétablissez la sonde ou coupez la gestion du boiler ; FoxCat lit 0 °C et peut chauffer à tort |
| Machines allumées alors que le prix est haut, boiler coupé | Mode Backup actif (Internet coupé) | Vérifiez le capteur « Internet en ligne » ; rétablissez la connexion ou coupez l'interrupteur « Mode Backup si Internet coupé » |
| Flux de prix en `DEGRADE` | Plus de prix reçus et tampon épuisé | Rétablissez Internet ou l'intégration de prix ; le boiler reste en repli confort 45 °C |
| Prix actif à 0 ou « — » | Prix non saisis, capteur indisponible | Vérifiez l'écran **Contrat et réseau** et vos capteurs de prix |
| Coûts trop élevés ou trop faibles | Case « tout compris » mal réglée | Cochez-la si votre prix inclut réseau, taxes et marge ; décochez sinon |
| « Pas encore de données » dans le comparateur | Historique insuffisant | Attendez quelques heures de mesure |
| Comparateur : « kWh sans prix » | Créneaux sans prix connu | Vérifiez la continuité de vos capteurs de prix ; FoxCat n'invente aucun prix |
| Capteur « Comparateur » ou « Coûts réseau » introuvable | Intégration non mise à jour | Mettez à jour, redémarrez, rechargez l'intégration |
| Les graphiques de prix sont vides | Prix dynamique non lu | Vérifiez les entités de **Tarification dynamique** et le capteur **Price Analyzer V2** |
| Le boiler ne chauffe pas | Sécurité thermique, mode Manuel, gestion coupée | Contrôlez la température de la résistance, le mode EMS et « Boiler géré par FoxCat » |
| Une machine reste à l'arrêt | Hors fenêtre, ou cycle protégé | Vérifiez la **fenêtre machines** et le statut de la machine |
| Le délestage oscille | Seuils trop proches | Écartez les seuils de déclenchement et de réarmement, ou allongez les trames de confirmation |
| Les modifications du menu ont disparu | Fenêtre fermée sans enregistrer | Terminez toujours par **« Enregistrer et quitter »** |
| Le dashboard n'apparaît pas | Dashboard non déclaré | Fusionnez `configuration.yaml.snippet` et redémarrez |
| Commandes qui se contrarient | Une ancienne automatisation pilote le même équipement | Désactivez-la |

### Aller plus loin

- Le **mode développeur** (Mesures et sources → Avancé) active les diagnostics avancés et les scénarios de simulation, sans effet sur les décisions réelles.
- Les capteurs de l'appareil **Système** donnent l'état du moteur, du métronome et du bus.

---

## 14. Retour arrière

**En cas de doute, dans cet ordre :**

1. Mettez **Régulation FoxCat active = OFF**.
2. Appuyez sur **« Libérer l'onduleur à 100 % »**.
3. Passez le **Mode EMS** sur **Manuel**.
4. Si nécessaire, restaurez la version précédente de l'intégration (HACS) et rechargez un profil sauvegardé.
5. Pour le dashboard : restaurez `dashboard.yaml.bak`, ou choisissez la version précédente dans le sélecteur.

> FoxCat n'est pas un dispositif de sécurité certifié : gardez vos protections matérielles (disjoncteurs, thermostats de sécurité) en place.
