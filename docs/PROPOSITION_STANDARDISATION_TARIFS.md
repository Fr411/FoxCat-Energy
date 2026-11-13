# Proposition : configurateur de tarification et comparateur (Belgique)

Source de référence : « Guide des Tarifs et Contrats d'Énergie en Belgique » (nov. 2026).

## 1. Constat : ce que FoxCat suit déjà

| Élément du guide | Dans FoxCat | État |
|---|---|---|
| Contrat fixe / variable / dynamique | `price_source` (contractuelle, variable, intégration, Day-Ahead) | Couvert |
| Wallonie mono-horaire | `distribution_profile = Simple` | Couvert |
| Wallonie bi-horaire 2026 (nuit + 11h-17h, 7j/7) | `tariff_hp_*` : HP 07-11 et 17-22, HC le reste | Couvert (défauts corrects) |
| Wallonie Impact (5 plages, 3 niveaux) | `impact_*` : ECO 01-07 et 11-17, PIC 17-22, MEDIUM | Couvert |
| Complément réseau par plage | `tariff_tou_hp/hc_adder`, `impact_*_adder` | Couvert |
| Réinjection (compensation, facturée, zéro, non valorisée) | `network_policy` | Couvert |
| Prosumer wallon (redevance) | rien | Absent |
| Flandre : tarif capacitaire (moyenne mensuelle des pointes 1/4 h, min 2,5 kW) | rien (le délestage protège le disjoncteur, pas ce coût) | Absent |
| Bruxelles : forfait capacitaire (~47 €/an, x2 au-delà de 13 kVA) | rien | Absent |

## 2. Problèmes constatés

1. **Les listes déroulantes figent des combinaisons.** Famille « HP/HC » = Mono ou Bi ; famille « Dynamique » = Simple ou Impact. Impossible d'avoir Impact avec un contrat fixe, ou bi-horaire avec un contrat dynamique, alors que le moteur sépare déjà contrat (`price_source`) et réseau (`distribution_profile`).
2. **Prix HP et HC obligatoires** en bi-horaire (`config_flow.py`), même avec un prix de fourniture unique.
3. **Capteurs par défaut codés en dur** sur un fournisseur (`sensor.luminus_luminus_dynamic_wallonia_*`, `config_flow.py` et `runtime/registry.py`).
4. **Aucune notion de région ni de gestionnaire de réseau.**
5. **Le ledger ne permet pas de comparer des tarifs.** `domain/accounting/manager.py` calcule le coût à l'instant avec le prix du tarif actif, puis l'additionne dans des totaux jour/mois/année. Rien ne permet de rejouer un autre tarif.
6. **Pas de coût capacitaire** (Flandre, Bruxelles) ni de redevance prosumer (Wallonie).

## 3. Proposition : un configurateur de tarifs

### 3.1 Un tarif = un ensemble de composantes

| Composante | Options |
|---|---|
| Prix d'énergie | fixe ; par plages horaires ; entité Home Assistant au choix ; Day-Ahead + marge |
| Plages horaires | tableau (début, fin, jours, prix ou complément) : mono, bi-horaire, Impact, jour/nuit sont des tableaux différents, pas des modes différents |
| Terme capacitaire | moyenne mensuelle des pointes 1/4 h avec minimum (Flandre) ; forfait selon la puissance (Bruxelles) |
| Frais fixes | abonnement, redevance prosumer |
| Réinjection | prix fixe, entité, ou nul |

L'utilisateur peut définir plusieurs tarifs. Un seul est « actif » et pilote l'optimiseur (ballon, machines). Les autres servent à comparer.

### 3.2 Modèles prédéfinis

Les listes déroulantes actuelles deviennent des modèles de départ (« Wallonie bi-horaire 2026 », « Wallonie Impact », « Flandre capacitaire », « Dynamique Day-Ahead »). Un modèle remplit le tableau en un clic, puis tout reste modifiable, y compris les entités de prix. Les valeurs chiffrées changent chaque année et restent éditables.

### 3.3 Import / export JSON

Un tarif ou une configuration complète s'exporte en JSON et s'importe sur une autre installation. C'est le moyen de standardiser plusieurs installations sans ressaisie.

### 3.4 Interface dans Home Assistant

Un `config_flow` n'a pas d'éditeur de tableau. On utilise un flux d'options en menu : ajouter / éditer / supprimer un tarif, ajouter / éditer / supprimer une plage. Plus verbeux qu'une liste, mais sans limite de combinaisons.

## 4. Comparateur

### 4.1 Prérequis techniques

1. **Série de consommation par quart d'heure** : import, export, PV, maison (environ 96 lignes par jour, quelques Mo par an). Elle sert aussi au calcul du capacitaire, qui a besoin des pointes par quart d'heure.
2. **Historique du prix spot de chaque créneau**, enregistré au moment de la mesure. Sans lui, un contrat dynamique ne peut pas être rejoué après coup.
3. **Fonction de valorisation pure** : (série, définition de tarif) → coût détaillé par composante. Appliquée à N tarifs en parallèle, sans toucher au moteur.

### 4.2 Sorties

Coût par tarif sur jour / mois / année et écart par rapport au tarif actif, exposés en capteurs et en carte dashboard.

### 4.3 Limites à afficher

- Le comparateur est **à comportement constant** : FoxCat décale le ballon et les machines selon le tarif actif. Ce que l'utilisateur aurait consommé sous un autre tarif serait différent. Le résultat compare la consommation réellement mesurée, il ne simule pas un autre mode de vie.
- Les tarifs comparés doivent être saisis avec les mêmes composantes (taxes, marge, réseau) pour que l'écart soit honnête.

## 5. Sources de prix : ENTSO-E et Nord Pool

FoxCat a déjà des champs pour le prix courant, le suivant, min/max/moyenne du jour et du lendemain, et un indicateur « prix de demain disponible » (`CONF_PRICE_*` dans `const.py`). Le configurateur doit permettre de **charger la liste des entités ENTSO-E et Nord Pool** détectées dans Home Assistant et de proposer l'association automatique ci-dessous.

Les identifiants contiennent un préfixe propre à chaque installation (`<préfixe>`), jamais à coder en dur.

### 5.1 ENTSO-E (à retenir)

| Entité | Usage dans FoxCat |
|---|---|
| `sensor.<préfixe>_current_electricity_market_price` | Prix courant et, selon l'intégration, source de la courbe (attributs) |
| `sensor.<préfixe>_next_hour_electricity_market_price` | Prix suivant (`price_next`) |
| `sensor.<préfixe>_average_electricity_price` | Moyenne du jour (`price_avg_today`) |
| `sensor.<préfixe>_lowest_energy_price` | Minimum du jour (`price_min_today`) |
| `sensor.<préfixe>_highest_energy_price` | Maximum du jour (`price_max_today`) |
| `sensor.<préfixe>_current_percentage_in_electricity_price_range` | Position dans la plage du jour : alimente directement le seuil de position de l'optimiseur dynamique |
| `sensor.<préfixe>_time_of_lowest_price` / `..._time_of_highest_price` | Heures des extrêmes, pour planifier les chauffes |

À ignorer : `current_percentage_of_highest_electricity_price` (redondant avec la position dans la plage).

### 5.2 Nord Pool (à retenir)

| Entité | Usage dans FoxCat |
|---|---|
| `sensor.nord_pool_be_prix_actuel` | Prix courant |
| `sensor.nord_pool_be_prochain_prix` | Prix suivant |
| `sensor.nord_pool_be_prix_le_plus_bas` / `..._le_plus_eleve` | Min / max du jour |
| `sensor.nord_pool_be_moyenne_journaliere` | Moyenne du jour |
| `binary_sensor.nord_pool_be_prix_de_demain_disponible` | **Déclencheur de publication** : indique que les prix du lendemain sont publiés (`price_tomorrow_available`) |
| `sensor.nord_pool_be_derniere_mise_a_jour` | Fraîcheur des données : sert de garde-fou si la publication est en retard |
| `sensor.nord_pool_be_devise` et `sensor.nord_pool_be_taux_de_change` | Contrôle d'unité (€/MWh ou €/kWh) avant toute valorisation |

Secondaires (non préassociés) : `prix_precedent`, les blocs peak / off-peak (`moyenne_peak`, `off_peak_1/2_*`, `debut/fin_heure_creuse/pleine`). Utiles pour un affichage, pas pour le calcul.

### 5.3 Points à vérifier avant de coder

- **Les séries horaires.** Les capteurs Nord Pool listés donnent des valeurs ponctuelles, pas la courbe complète. Pour la courbe du lendemain, il faut soit les attributs de l'entité ENTSO-E, soit l'action de l'intégration Nord Pool. Il faut lire les attributs réels dans Outils de développement > États.
- **Clés d'attributs.** Le lecteur de courbe (`extract_price_points`) accepte `prices`, `forecast`, `raw_today`, `raw_tomorrow`, `today`, `tomorrow`, etc. Si ENTSO-E nomme ses séries autrement (par exemple `prices_today`), il faudra ajouter ces clés.
- **Prix spot ≠ prix payé.** Les prix de marché n'incluent ni marge du fournisseur, ni réseau, ni taxes : ces composantes viennent du tarif configuré (section 3).
- **Moment de publication.** Les prix du lendemain sont publiés dans l'après-midi (vers 13h). Le déclencheur est `prix_de_demain_disponible`, pas une heure fixe.

## 6. Migration

Les réglages actuels (`price_source`, `tariff_structure`, `distribution_profile`, plages, compléments) sont convertis en un premier tarif « actif », sans changer le comportement des installations existantes. Les listes déroulantes disparaissent de l'installation au profit des modèles ; les entités `select` actuelles restent lisibles pendant une version de transition.

## 7. Ordre de réalisation

1. Modèle de données « tarif » + fonction de valorisation, avec tests (aucun changement visible).
2. Série par quart d'heure + historique spot ; migration vers un tarif actif.
3. Flux de configuration, modèles prédéfinis, import/export JSON, suppression des défauts Luminus.
4. Détection des entités ENTSO-E / Nord Pool et association automatique (section 5).
5. Comparateur : capteurs et carte dashboard.
6. Coûts capacitaire (Flandre), forfait (Bruxelles), redevance prosumer (Wallonie).

## 8. À valider

- La liste des composantes d'un tarif (section 3.1).
- Les plages Flandre et Bruxelles ne figurent pas dans le guide : valeurs à obtenir auprès de Fluvius et de Sibelga pour les modèles.
- Les montants du guide sont des moyennes : l'utilisateur doit pouvoir saisir les siens.
