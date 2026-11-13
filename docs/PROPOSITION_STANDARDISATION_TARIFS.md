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
7. **Risque de double comptage avec une source tout compris** : `final_client_price` ajoute les compléments de distribution même sur une courbe déjà finale (détail en section 5.3).

## 3. Proposition : un configurateur de tarifs

### 3.1 Un tarif = un ensemble de composantes

| Composante | Options |
|---|---|
| Prix d'énergie | fixe ; par plages horaires ; entité Home Assistant au choix, éventuellement marquée « tout compris » (voir section 5) ; Day-Ahead + marge |
| Plages horaires | tableau (début, fin, jours, prix ou complément) : mono, bi-horaire, Impact, jour/nuit sont des tableaux différents, pas des modes différents |
| Terme capacitaire | calculé par FoxCat (moyenne mensuelle des pointes 1/4 h avec minimum en Flandre ; forfait selon la puissance à Bruxelles) ou lu depuis l'intégration de prix si elle le fournit |
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

## 5. Sources de prix et signaux de publication

Principe : **prix** et **publication** viennent de deux sources différentes.

- **ENTSO-E et Nord Pool sont des prix de gros** (spot) : ni réseau, ni taxes, ni marge. Ils ne doivent jamais être utilisés comme prix payé. Dans le configurateur, ils ne remplissent pas les champs de prix.
- **Le prix payé vient d'une intégration de prix tout compris**, ici `homeassistant_be_electricity_prices` (renaudallard). ENTSO-E / Nord Pool servent uniquement à savoir **quand** les prix du lendemain sont publiés.

### 5.1 L'intégration de prix tout compris (faits relevés dans sa documentation)

| Élément | Détail |
|---|---|
| Prix | `current_price`, `next_hour_price`, min/max/moyenne du jour et du lendemain, en EUR/kWh, **tout compris** (énergie + distribution + transport + taxes + TVA) |
| Décomposition | `energy_component`, `network_component`, `taxes_component` |
| Courbe | attributs `today` et `tomorrow` de `current_price` : lignes `{start, energy, network, taxes, all_in}` (96 lignes/jour pour un contrat au quart d'heure) |
| Injection | `injection_price` (attributs `today` / `tomorrow`), et variantes pointe / creuse |
| Bi-horaire | `price_peak`, `price_offpeak` (non créés pour le tarif Impact wallon) |
| Publication | binaire `tomorrow_prices_available` ; mise à jour **horaire** ; courbe du lendemain attendue vers 13h CET |
| Coûts calculés | `capacity_cost` et `monthly_peak_kw` (Flandre), `prosumer_cost` (Wallonie), `current_month_cost`, `current_year_cost`, `potential_saving` |
| Services | `refresh`, `cheapest_window`, `most_expensive_window` |
| Couverture | fournisseurs belges des trois régions, contrats fixes, variables, dynamiques, bi-horaires et Impact |

Source : README et `docs/entities.md` du dépôt. La fin de ces deux documents n'a été lue que par résumé : les noms exacts des attributs d'injection et le détail du binaire sont à confirmer sur l'installation réelle.

### 5.2 Compatibilité avec FoxCat

- Le lecteur de courbe de FoxCat (`extract_price_points`) lit déjà `today` / `tomorrow`, la clé de temps `start`, et la clé de prix `all_in` (utilisée à l'origine pour Luminus). La courbe de `current_price` devrait donc être lisible telle quelle.
- FoxCat a déjà un champ « prix de demain disponible » (`price_tomorrow_available`) : on peut y associer `tomorrow_prices_available`.

### 5.3 Piège : double comptage de la distribution

Avec une source tout compris, le réseau et les taxes sont **déjà dans le prix**. Or `final_client_price` (`domain/tariff/tariff_model.py`) ajoute encore les compléments `tariff_tou_hp/hc_adder` et `impact_*_adder` selon la période, même quand `price_curve_is_final` est vrai. Si ces compléments ne sont pas à zéro, la distribution est comptée deux fois.

Règle du configurateur : une composante de prix marquée « tout compris » désactive automatiquement les compléments réseau, taxes et marge de ce tarif.

### 5.4 Rôle d'ENTSO-E et Nord Pool : signaux de publication

Le délai actuel peut atteindre une heure : l'intégration de prix ne relit qu'à chaque tick horaire. Les signaux de gros sont plus rapides.

| Entité | Rôle |
|---|---|
| `binary_sensor.nord_pool_be_prix_de_demain_disponible` | Déclencheur : les prix de gros du lendemain sont publiés |
| `sensor.nord_pool_be_derniere_mise_a_jour` | Horodatage de la dernière publication, garde-fou de retard |
| ENTSO-E : prix de l'heure suivante, moyenne, min, max, heures des extrêmes | Contrôle de cohérence (le tout compris doit suivre le spot) et affichage, pas de valorisation |

Flux proposé : le signal de publication passe à « disponible » → FoxCat appelle le service `refresh` de l'intégration de prix (nom exact du domaine de service à confirmer) → attend `tomorrow_prices_available` → relit la courbe du lendemain → relance la planification. Si le signal n'arrive pas, le tick horaire de l'intégration reste le filet de sécurité.

Les entités ENTSO-E / Nord Pool sont donc **optionnelles** dans le configurateur, présentées comme « signal de publication », jamais comme « prix ».

### 5.5 Conséquences sur le reste de la proposition

- **Moins de calcul dans FoxCat.** Pour un utilisateur de cette intégration, le coût capacitaire flamand et la redevance prosumer wallonne sont fournis par ses capteurs. FoxCat les lit au lieu de les recalculer. Le calcul interne (section 3.1) reste pour les installations sans cette intégration.
- **Deux sources de vérité pour les coûts.** `current_month_cost` de l'intégration et le ledger FoxCat ne mesurent pas forcément la même chose. Le tableau de bord doit indiquer laquelle est affichée.
- **Comparateur.** L'intégration donne le prix du contrat configuré, et son propre `potential_saving`. Pour comparer plusieurs tarifs dans FoxCat, il faut soit plusieurs instances de l'intégration (à vérifier), soit des tarifs saisis manuellement dans le configurateur. Le comparateur FoxCat reste utile car il applique la comparaison à la consommation réelle mesurée par FoxCat.

## 6. Migration

Les réglages actuels (`price_source`, `tariff_structure`, `distribution_profile`, plages, compléments) sont convertis en un premier tarif « actif », sans changer le comportement des installations existantes. Les listes déroulantes disparaissent de l'installation au profit des modèles ; les entités `select` actuelles restent lisibles pendant une version de transition.

## 7. Ordre de réalisation

1. Modèle de données « tarif » + fonction de valorisation, avec tests (aucun changement visible).
2. Série par quart d'heure + historique spot ; migration vers un tarif actif.
3. Flux de configuration, modèles prédéfinis, import/export JSON, suppression des défauts Luminus.
4. Association de l'intégration de prix tout compris, marquage « tout compris » (fin du double comptage) et signal de publication ENTSO-E / Nord Pool (section 5).
5. Comparateur : capteurs et carte dashboard.
6. Coûts capacitaire (Flandre), forfait (Bruxelles), redevance prosumer (Wallonie).

## 8. À valider

- La liste des composantes d'un tarif (section 3.1).
- Les plages Flandre et Bruxelles ne figurent pas dans le guide : valeurs à obtenir auprès de Fluvius et de Sibelga pour les modèles.
- Les montants du guide sont des moyennes : l'utilisateur doit pouvoir saisir les siens.
