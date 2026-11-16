# 05 · Prix dynamiques : séries de prix, Price Analyzer, décision économique, Day-Ahead

> Sources : `domain/pricing/economic_optimizer.py`, `domain/pricing/price_analyzer.py`, `domain/pricing/dynamic_scheduler.py`, `runtime/coordinator.py` (`_economic_view`, `_economic_import_points`, `_economic_export_points`, `_economic_series_from_entity`, sauvegarde de prix).
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

## 1. Chaîne de calcul

```text
entités de prix ──► série de points (PricePoint) ──┬─► Price Analyzer      → fenêtres favorables, pics, statistiques
                                                   ├─► décision économique → bande BAS/MEDIAN/HAUT, réservation boiler
                                                   ├─► planificateur Day-Ahead → créneaux machines
                                                   └─► planificateur de charges flexibles (voir 07)
```

Tout est recalculé par `_economic_view` à chaque reconstruction des données (donc à chaque trame et à chaque événement) ; seul le comparateur de tarifs est mis en cache.

## 2. Construction des séries de prix

Un `PricePoint` = (instant, prix €/kWh, origine).

### 2.1 Prix d'achat (`_economic_import_points`)

| Situation | Série produite |
|---|---|
| contrat **dynamique** | courbe lue dans l'entité « prévision d'import » ou, à défaut, « prix actuel » ; complétée par le prix actif (créneau de l'heure courante) et le prix suivant (heure +1) |
| **bi-horaire** non dynamique | `build_hphc_points` : un point **toutes les 15 min** sur l'horizon, prix HP ou HC selon `tariff_period` |
| **mono / Impact** non dynamique | un point **par heure**, prix fixe saisi (ou prix lu) passé par `final_client_price` (donc avec les compléments de période) |

Horizon : **36 h** en dynamique (`DYNAMIC_ARBITRAGE_HORIZON_HOURS`), sinon `economic_horizon_hours` (24 h).

### 2.2 Extraction depuis une entité (`extract_price_points`)

Parcours récursif des attributs :

- dictionnaire : prix = première clé trouvée parmi les clés préférées (`all_in` pour l'achat, `injection` pour la réinjection) puis `price`, `value`, `total`, `price_eur_kwh`, `eur_kwh`, `eur_per_kwh`, `import_price`, `export_price`, `marketprice`, `prijs` ; instant = première clé de temps lisible ; sous-séries `today`/`raw_today` (base minuit), `tomorrow`/`raw_tomorrow` (base lendemain minuit) ;
- liste de 2 éléments `[instant, prix]` ;
- **liste numérique simple** : une valeur par **heure** à partir du début de l'heure courante.

Seuls les points entre « maintenant − 1 h » et l'horizon sont conservés ; les doublons d'instant sont écrasés (le dernier gagne). **Aucun prix n'est inventé** : une entité absente ou illisible ne produit aucun point.

Une fois extraits, les points d'achat passent par `apply_final_price_components` (compléments réseau/taxes/périodes, sauf `price_is_all_in`).

### 2.3 Sauvegarde des prix (intégration externe seulement)

Avec la source « Intégration externe », FoxCat mémorise les points futurs (jusqu'à 36 h) à chaque changement de prix et les relit si l'entité devient indisponible. Les points passés ou hors horizon sont purgés. Aucune sauvegarde pour les autres sources.

### 2.4 Prix de réinjection (`_economic_export_points`)

Série de la **valeur** de la réinjection (positive = recette), lue comme l'achat avec la clé préférée `injection`, sinon construite à partir du prix fixe ou de 0 selon la politique.

## 3. Price Analyzer V2 (`analyze_price_curve`)

Actif seulement pour un tarif dynamique (sinon l'état vaut `INACTIF`, `series` vide). Il **ne fabrique aucune valeur manquante**.

### 3.1 Découpage

- `granularité` = médiane des écarts entre points (1 à 360 min), 60 min par défaut.
- Points d'aujourd'hui, de demain, d'hier ; « futurs » = ceux dont l'instant ≥ `maintenant − granularité`.

### 3.2 Position, rang, statistiques

```text
prix courant   = prix actif (si fourni) sinon le dernier point passé
position (%)   = (courant − min des points futurs) ÷ (max − min) × 100      (50 % si min = max)
rang           = 1 + nombre de points futurs strictement moins chers que le courant
```

La position utilise **tous les points futurs** (aujourd'hui + demain), alors que les fenêtres favorables utilisent le **min/max du jour** (§ 3.3) : les deux échelles diffèrent.

### 3.3 Fenêtres favorables

```text
seuil   = dynamic_favorable_position_pct (30 %) ; durée max = dynamic_favorable_max_hours (4 h)
positions calculées sur le min/max d'AUJOURD'HUI
candidats = points d'aujourd'hui dont la position ≤ seuil, triés du moins cher au plus cher
sélection : on ajoute les points dans cet ordre tant que la durée cumulée ≤ 4 h (un point qui dépasse est sauté)
fenêtres  = regroupement des points sélectionnés (un trou > ½ granularité ouvre une nouvelle fenêtre)
état      = IN_FAVORABLE_WINDOW / BEFORE_FAVORABLE_WINDOW / AFTER_FAVORABLE_WINDOW
```

Durée d'un point = écart jusqu'au point suivant (s'il est ≤ 1,5 × granularité), sinon la granularité.

### 3.4 Pics

Un point futur est un **pic** si sa position (échelle future) ≥ `dynamic_high_position_pct` (70 %) et qu'il est un maximum local (≥ voisins, strictement > l'un d'eux).

### 3.5 Prédictif ou réactif

`PREDICTIVE` si « prix de demain disponible » (capteur dédié, ou présence de points de demain), si des points de demain existent et si la courbe est **continue** (écart maximal entre points futurs ≤ 2,5 × granularité). Sinon `REACTIVE`. `valid` = points présents et courbe continue.

### 3.6 Autres sorties

Économie potentielle (prix courant − meilleur prix futur, ≥ 0), meilleur créneau restant aujourd'hui et demain, comparaison avec hier à la même heure et avec la moyenne d'hier, statistiques jour/demain/hier, et **la série complète** (`series` : instant, prix d'achat, prix de réinjection, favorable, pic) qui alimente les graphiques du tableau de bord.

## 4. Décision économique (`evaluate_market`)

Entrées : prix actifs (`prices()`), séries, instantané, modèle thermique du boiler. Ordre d'évaluation :

| # | Condition | Décision |
|---|---|---|
| 1 | `economic_optimizer_enabled` faux | `DESACTIVE` (démarrage flexible autorisé) |
| 2 | politique **Compensation** et régime non dynamique | `COMPENSATION_MAX_PV` : produire au maximum |
| 3 | prix d'achat inconnu | `PRIX_INDISPONIBLE` : aucune décision chiffrée |
| 4 | régime **dynamique** | `_evaluate_dynamic_market` (§ 5) |
| 5 | non dynamique | baseline HP/HC (§ 6) |

Confiance : `HAUTE` si régime bi-horaire avec prix connu ou ≥ 6 points ; `MOYENNE` si ≥ 2 points ; sinon `FAIBLE`.

## 5. Marché dynamique (`_evaluate_dynamic_market`)

### 5.1 Courbe de référence

Les points d'achat sont **ramenés à un point par heure** (`_dynamic_day_ahead_points`) sur 36 h à partir de l'heure courante, complétés par le prix courant. Pour des prix au quart d'heure, chaque heure vaut la **moyenne de ses points** (corrigé A-16 ; auparavant seul le dernier point de l'heure était conservé). Moins de 6 points, ou « prédictif » désactivé → repli standard (§ 5.2).

### 5.2 Repli standard (`_legacy_dynamic_decision`)

Seuils : économie minimale 0,02 €/kWh, marge de réinjection 0,01 €/kWh, surplus minimal 250 W (`has_surplus = export ≥ 250 W`).

| Condition | Code |
|---|---|
| surplus et réinjection négative | `ABSORBER_SURPLUS` |
| surplus et réinjection > meilleur achat futur + marge | `EXPORTER_ET_REPORTER` |
| surplus et réinjection + marge < prix d'achat | `AUTOCONSOMMER` |
| prix d'achat négatif | `PRIX_ACHAT_NEGATIF` (consommer) |
| économie > 0,02 € et meilleur créneau dans plus de 10 min | `ATTENDRE_MEILLEUR_PRIX` |
| sinon | `CONSOMMER_MAINTENANT` |

### 5.3 Décision prédictive

```text
index = (prix courant − min) ÷ (max − min)  borné 0–1      (0,5 si max = min)  → position_pct = index × 100
bande : BAS si index ≤ bas ; HAUT si index ≥ haut ; sinon MEDIAN
        bas = 35 %, haut = 70 %   (constantes DYNAMIC_POSITION_LOW / HIGH)
rang = 1 + nombre de prix horaires strictement inférieurs ; tendance = moyenne des 3 prochaines heures vs prix courant ± dynamic_price_significant_delta (0,01)
```

Les seuils réglables `dynamic_favorable_position_pct` et `dynamic_high_position_pct` ne remplacent ces constantes **que si `mode = Dynamique`**, ce qui n'arrive plus (A-02) : la bande et la décision de charge de ce bloc utilisent donc toujours 35 % / 70 % (A-17). Le boiler dynamique, l'analyseur de prix et le planificateur Day-Ahead lisent, eux, les réglages utilisateur.

Autoconsommation :

```text
avantage_autoconsommation = prix d'achat − valeur de réinjection
prefer_export            = surplus ET réinjection > 0 ET avantage < −marge
prefer_self_consumption  = surplus ET (réinjection inconnue OU négative OU avantage ≥ −marge)
```

### 5.4 Réservation du boiler

```text
énergie manquante (kWh) et durée de chauffe (h)  = modèle thermique (voir 02)
fenêtre réservée = bloc d'heures CONSÉCUTIVES le moins cher (moyenne minimale) couvrant ⌈durée⌉ heures ; une heure manquante invalide le candidat
réservation active = énergie manquante > 0 ET l'heure courante est dans la fenêtre réservée
priorité confort = température < reprise (43 °C) ET énergie manquante > 0
charge_now :
    = réservation active ET index ≤ bas
    OU énergie manquante ET bande MEDIAN ET surplus ET « financièrement favorable maintenant »
    OU énergie manquante ET surplus solaire ≥ puissance de la résistance (solar_only_now)
    OU priorité confort
financièrement favorable = coût effectif du boiler maintenant ≤ coût en plein réseau au meilleur créneau + marge × puissance
coût effectif (€/h) = (réseau nécessaire) × prix d'achat + (solaire utilisé) × valeur de réinjection
```

### 5.5 Codes de décision

| Priorité | Condition | Code | `flexible_start` |
|---|---|---|---|
| 1 | priorité confort ECS | `ECS_PRIORITAIRE` | non |
| 2 | bande BAS | `DYNAMIC_BAS` | `non charge_now` |
| 3 | bande MEDIAN | `DYNAMIC_MEDIAN` | surplus et non `charge_now` |
| 4 | bande HAUT | `DYNAMIC_HAUT` | non |

## 6. Baseline non dynamique

Mêmes seuils que le repli standard, puis : période **HC** → `CONSOMMER_HC` ; économie > 0,02 € → `ATTENDRE_HC` ; sinon `HP_ACCEPTABLE`.

## 7. Recommandation par machine (`recommend_flexible_load`)

Calculée pour chaque machine pilotable, à partir de l'énergie et de la durée apprises (moyenne des 10 derniers cycles ; défaut 1 h et 1 kWh).

- Cycle protégé en cours : `CYCLE_EN_COURS`, démarrage autorisé (jamais interrompu).
- Prix indisponible : `PRIX_INDISPONIBLE`, démarrage refusé.
- Sinon : meilleur créneau de départ sur l'horizon (moyenne des prix sur la durée du cycle, échantillonnée toutes les 15 min), coût effectif maintenant (part solaire × valeur de réinjection + part réseau × prix moyen), économie.
- **Dynamique prédictif** (selon la bande de la décision économique) :

| Bande | Règle |
|---|---|
| ECS prioritaire ou charge boiler en cours | refus `PRIORITE_ECS` |
| HAUT | autorisé seulement si du solaire est présent **et** coût effectif ≤ coût futur + économie minimale |
| MEDIAN | autorisé si surplus ≥ puissance moyenne, ou solaire présent et financièrement meilleur |
| BAS | autorisé si financièrement meilleur maintenant ou sans meilleur créneau connu |

- Autres cas (baseline) : surplus ≥ 50 % avec réinjection négative → démarrer ; surplus ≥ 50 % avec réinjection > meilleur coût futur + marge → exporter et reporter ; économie > 0,02 € avec meilleur créneau dans plus de 10 min → reporter ; sinon démarrer.

Cette recommandation est **enrichie** par le planificateur de charges flexibles (voir `07`), qui est le décideur final de `allow_start`.

## 8. Planificateur Day-Ahead (`build_dynamic_schedule`)

Actif si : tarif dynamique, mode ≠ Manuel, optimiseur économique actif et « prédictif prix dynamique » actif. Sinon : `active: false`. (Le libellé interne « hors mode Dynamique » est un reste de l'ancien mode, voir A-02.)

Paramètres : seuil favorable (30 %, borné 5–60), seuil pic (70 %, ≥ favorable, ≤ 95), horizon = min(dernier point + 1 h, maintenant + 36 h).

Calcul :

1. `pmin`, `pmax` sur les points de « maintenant − 1 h » à la fin ; position courante = position de la décision économique (sinon recalculée) ; `favorable_now` = position ≤ seuil.
2. **Fenêtre solaire** : plage horaire de la prévision solaire (si disponible) pour préférer les créneaux solaires (`solar_forecast_arbitrage`).
3. **Creux et pic** : premier bloc de points dont la position ≤ seuil favorable (creux) et ≥ seuil pic (pic). Les blocs sont rattachés tant que deux points sont à moins de 90 min ; la **fin du bloc est le dernier point + 1 h** (suppose des points horaires, A-16).
4. **Par machine** (profil appris sinon durée configurée, minimum 0,25 h) :
   - fenêtres utilisateur = deux plages configurées de la machine (défauts 21:30–07:00 et 10:30–17:00), étendues sur l'horizon ;
   - candidats de départ **toutes les 15 min** dans ces plages tant que le cycle entier tient ;
   - candidat retenu : d'abord favorable, puis chevauchement solaire maximal, puis prix moyen le plus bas, puis le plus tôt ;
   - décision immédiate, par priorité : cycle protégé → `CYCLE_EN_COURS` (autorisé) ; hors plage utilisateur → `HORS_PLAGE_UTILISATEUR` ; confort ECS prioritaire → `PRIORITE_ECS` ; surplus couvrant ≥ 50 % de la puissance moyenne apprise → `DEMARRAGE_AUTOCONSOMMATION` ; prix favorable maintenant → `DEMARRAGE_PRIX_FAVORABLE` ; sinon `PLANIFIE` (attente).

## 9. Paramètres de cette page

| Réglage | Défaut | Effet réel |
|---|---|---|
| `dynamic_favorable_position_pct` | 30 % | analyseur, boiler dynamique, planificateur ; **pas** la bande de la décision économique (A-17) |
| `dynamic_high_position_pct` | 70 % | idem |
| `dynamic_favorable_max_hours` | 4 h | durée cumulée des fenêtres favorables |
| `dynamic_price_significant_delta` | 0,01 | seuil de tendance |
| `economic_horizon_hours` | 24 h | horizon non dynamique |
| `economic_min_saving_eur_kwh` | 0,02 | économie minimale pour reporter |
| `economic_export_margin_eur_kwh` | 0,01 | marge de réinjection |
| `economic_solar_surplus_min_w` | 250 W | surplus minimal |
| `economic_optimizer_enabled` / `predictive_pricing_enabled` / `solar_forecast_arbitrage` | oui | interrupteurs |
| `dynamic_grid_charge_threshold_eur_kwh`, `dynamic_negative_price_charge_enabled` | 0 / oui | « charge réseau si prix dynamique négatif » : **sans effet**, lus uniquement par du code inatteignable (A-03). Le boiler dynamique ne chauffe jamais le réseau au-delà de 45 °C et n'a pas de règle « prix négatif » |
| `dynamic_preferred_network_max_eur_kwh` | 0,30 | **sans effet** (A-03) |

## 10. Couverture par les tests

`tests/test_dynamic_analysis.py` couvre l'analyseur, la décision dynamique et la migration ; `tests/test_peak_runtime.py` et `tests/test_vpp.py` couvrent des fonctions voisines. **Non couverts** : `extract_price_points` sur des courbes au quart d'heure, `_best_consecutive_dynamic_window`, `recommend_flexible_load`, `build_dynamic_schedule`.


## Fonctionnement hors ligne (coupure Internet)

**Principe local-first.** Le cerveau de FoxCat tourne dans Home Assistant : mesures, métronome, boiler, PRI et machines passent par le réseau local. Seules les sources de prix de bourse, la prévision solaire en ligne et la tâche IA dépendent d'Internet.

**Tampon des prix.** Les prix du lendemain sont publiés vers 14 h. À chaque événement de l'entité de prix, `_capture_economic_price_backup` enregistre la courbe (import et injection) dans `price_backup` : fichier `.storage` de Home Assistant, relu au démarrage. Le tampon couvre 36 h vers l'avant (`DYNAMIC_ARBITRAGE_HORIZON_HOURS`) et garde 3 h de passé pour connaître la tranche en cours. Il s'applique aux sources `Dynamique Day-Ahead` et `Intégration externe`. Code pur : `domain/pricing/price_buffer.py`.

**États du flux de prix** (capteur « Flux de prix », `prices()["price_feed"]`) :

| État | Condition | Comportement |
|---|---|---|
| `EN_LIGNE` | l'entité de prix répond | prix en direct, tampon complété |
| `TAMPON` | entité indisponible, tampon couvre l'instant | prix courant, suivant et injection lus dans le tampon ; décisions Day-Ahead inchangées |
| `DEGRADE` | tampon épuisé | `PRIX_INDISPONIBLE` ; boiler en repli confort ; machines différées non lancées |
| `LOCAL` | contrat fixe, bi-horaire, Impact | aucune connexion nécessaire |

**Repli confort du boiler** (`dynamic_boiler_v2.py`). Sans position tarifaire exploitable : chauffe réseau à 45 °C si le ballon passe sous la reprise (43 °C), arrêt à 45 °C, jamais de BOOST réseau. Le BOOST solaire reste prioritaire.

**Mode Backup (coupure Internet).** Le tampon garde les décisions possibles, mais le mode Backup les remplace par la continuité de service :

| Élément | En Backup |
|---|---|
| Détection | `probe_internet` (TCP 443 vers 1.1.1.1, 8.8.8.8, 9.9.9.9) toutes les 30 s ; `ConnectivityMonitor` : hors ligne après N min d'échecs continus (`backup_offline_delay_min`, 2 par défaut), en ligne après 60 s de succès continus |
| Prises machines | `should_on` forcé (fenêtres, prix, planificateur, gestion désactivée ignorés), sauf délestage du disjoncteur |
| État avant coupure | mémorisé (`backup_state`, persistant) ; rétabli au retour sauf cycle protégé (`plan_restore`) |
| Boiler | `backup_boiler_intent` : reprise < 43 °C, arrêt 45 °C, jamais de BOOST réseau ; sécurité thermique prioritaire ; peak shaving, commande utilisateur et V2H passent avant |
| Onduleur (PRI) | libéré à 100 % et garde fermée, sauf politique « Zéro injection » |
| Inchangé | Manuel (aucune commande), régulation coupée, comptabilité (utilise le tampon) |

**Limites connues.** Au-delà de la fin du tampon, aucun prix n'est estimé (pas de « même heure hier »). La comptabilité compte 0 € d'achat quand aucun prix n'existe, et ne rattrape pas les prix réels au retour d'Internet. La prévision Forecast.Solar et la tâche IA solaire échouent hors ligne.
