# 06 · Comptabilité énergétique et financière

> Sources : `domain/accounting/manager.py` (ledger), `domain/accounting/__init__.py` (façade), `domain/accounting/series.py` (créneaux au quart d'heure), `_validation.py`, `bihoraire.py`, `dynamic.py`, `monohoraire.py`, `sensor.py` (capteurs et « Économiser avec FoxCat »), `runtime/coordinator.py` (appel à chaque trame).
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

## 1. Principe

La comptabilité est **observatrice** : elle ne décide rien et ne reçoit jamais de commande. À **chaque trame valide** de l'EMS Core (même régulation coupée), le coordinateur lui transmet l'instantané, les prix actifs et la liste des appareils. Elle sépare strictement :

- la **vérité physique** (kWh) : un revenu de réinjection n'est jamais converti en kWh, une réinjection ne diminue jamais un compteur d'import ;
- sa **valorisation financière** (€), calculée au prix actif au moment de la trame.

Deux structures indépendantes :

| Structure | Rôle | Résolution |
|---|---|---|
| **Ledger** (`EnergyAccounting`) | compteurs jour / mois / année / cumul | continue (à chaque trame) |
| **Série** (`ConsumptionSeries`) | kWh et prix par quart d'heure, 62 jours | 15 min ; alimente le comparateur de tarifs |

## 2. Intégration d'une trame (`EnergyAccounting.process`)

```text
1. rollover : si la date (jour / mois / année locale) a changé, le seau correspondant est remis à zéro
2. snapshot invalide        → last_valid_ts = None ; la trame n'est pas intégrée
3. première trame valide    → on mémorise l'instant, rien n'est intégré (aucune durée connue)
4. dt = now − dernier instant valide ; dt ≤ 0 ignoré ; dt plafonné à 3 600 s
5. énergies (kWh) = puissance de la trame × dt ÷ 3 600
```

L'intégration est un **rectangle** : la puissance *courante* est supposée constante sur tout l'intervalle écoulé depuis la trame précédente. Conséquences :

- un trou de mesure jusqu'à 1 h est intégré avec la **dernière** puissance connue ; au-delà de 1 h, seule la dernière heure l'est ;
- l'énergie d'une période où le snapshot était invalide est **perdue** (l'intervalle n'est pas rattrapé) ;
- au redémarrage de Home Assistant, `last_valid_ts` est remis à `None` : l'arrêt n'est jamais intégré.

### 2.1 Grandeurs physiques ajoutées à chaque seau

| Compteur | Calcul (puissances en W, `hours = dt ÷ 3600`) |
|---|---|
| `house_kwh` | `max(maison, 0) ÷ 1000 × hours` |
| `pv_kwh` | `max(PV, 0) ÷ 1000 × hours` |
| `import_kwh` / `export_kwh` | `max(import, 0)` / `max(export, 0)` ÷ 1000 × hours |
| `self_consumed_kwh` | `max(min(PV, maison), 0) ÷ 1000 × hours` |

Les compteurs physiques ne peuvent qu'augmenter (valeurs négatives ramenées à 0).

### 2.2 Grandeurs financières

```text
buy  = prix d'achat actif (prices()["active_buy"])      sell = valeur de réinjection (prices()["export_value"])
coût d'import       = import_kwh × buy                  (signé : un prix négatif donne un coût négatif)
valeur nette export = export_kwh × sell                 (signée)
revenu d'export     = max(valeur nette, 0)              coût d'export = max(−valeur nette, 0)
coût évité solaire  = autoconsommé_kwh × buy
```

Si `buy` ou `sell` est inconnu, le terme correspondant vaut 0 € (les kWh sont tout de même comptés).

### 2.3 Valeurs dérivées (`view`)

```text
autoconsommation % = autoconsommé ÷ PV                  autonomie % = autoconsommé ÷ maison
part réseau %      = import ÷ maison
coût net réseau    = coût d'import + coût d'export − revenu d'export
gain solaire       = coût évité + revenu d'export − coût d'export
```

## 3. Ventilation tarifaire (par seau)

La clé de ventilation dépend du **régime** (`prices()["regime"]`) :

| Régime | Seau |
|---|---|
| `Dynamique` | `tariff.dynamic` |
| `Bi-horaire (HP/HC)` | `tariff.hphc.HP` ou `.HC` selon `prices()["period"]` |
| autre (mono-horaire, Impact) | `tariff.other` |

Chaque seau compte import, export, coût d'import, revenu et coût d'export. La façade (`domain/accounting/__init__.py`) traduit le libellé public « Bi-horaire (HP/HC) » en « Bi-horaire HP/HC » attendu par le ledger historique ; sans cette traduction, le HP/HC tomberait dans `other`.

> Pour un contrat **dynamique** avec structure bi-horaire, la ventilation reste « dynamic » : il n'y a pas de découpage HP/HC.

## 4. Appareils (`_add_appliance`)

Pour chaque appareil fourni (machines suivies + chauffe-eau) dont la puissance est lisible et ≥ 0 :

```text
énergie  = puissance ÷ 1000 × hours
fraction_solaire = min(max(autoconsommé ÷ maison, 0), 1)           ← fraction au niveau de la MAISON, identique pour tous les appareils
solaire  = énergie × fraction_solaire          réseau = énergie − solaire
coût     = réseau × buy                         (signé)
hp_kwh / hc_kwh / dynamic_kwh / other_kwh = énergie selon régime et période
```

Un appareil n'est donc **pas** alimenté « réellement » par le solaire : on lui attribue la part solaire moyenne de la maison.

Le chauffe-eau est déclaré `managed` quand la **régulation est active** (indépendamment du mode) ; une machine l'est quand sa gestion automatique est active.

## 5. « Économiser avec FoxCat Energy » (`foxcat_*` dans chaque seau)

Calculé **uniquement** pour les appareils `managed` et quand `buy` est connu :

```text
gain solaire  = solaire_kWh × (buy − (sell ou 0))                           « solaire absorbé au lieu d'être revendu »
gain décalage = réseau_kWh × (prix de référence − buy)                      « réseau consommé sous le prix de référence »
prix de référence = HP (bi-horaire non dynamique) | moyenne du jour avec compléments (dynamique) | aucun
```

Sans prix de référence, le décalage vaut 0. Les gains sont **signés** (un décalage vers un prix plus cher se voit).
Capteurs : jour, mois, année ; attributs : solaire absorbé (€ et kWh), décalage (€ et kWh), gain par appareil, et la méthode. Batterie, VE et écrêtage de pointe ne sont pas inclus.

**Lecture à garder en tête** : c'est une attribution *par hypothèse*, pas une mesure contrefactuelle. Tout kWh réseau d'un appareil géré, consommé moins cher que la référence, est compté comme économie, même si l'utilisateur l'aurait fait à ce moment-là sans FoxCat ; la part solaire est la moyenne de la maison.

## 6. Persistance et rollover

- Format `schema: 2` ; migration automatique des anciens stores (≤ 1.6.157 : `export_value_eur` brut devient revenu/coût).
- Écriture : le coordinateur demande une sauvegarde au plus **toutes les 5 minutes** (`process` renvoie `True`), plus à d'autres événements (minuit, prix).
- Au redémarrage : `last_valid_ts = None` (voir § 2).
- `breakdown_since` : date de début de la ventilation tarifaire.

## 7. Contrôles de cohérence (lecture seule)

Après chaque trame, la façade valide la vue selon le régime et publie `accounting_checks` (`ok`, `warning` ou `error`) :

- compteurs physiques finis et non négatifs ; montants finis ;
- somme de la ventilation tarifaire ≤ compteur physique (erreur) ou incomplète (avertissement) ;
- appareils : solaire + réseau ≤ énergie (erreur), énergie non ventilée (avertissement) ;
- bi-horaire : HP + HC ≤ total, par horizon et par appareil ; dynamique : kWh dynamiques ≤ total ; mono-horaire : avertissement permanent « rangé dans `other` ».

Les validateurs ne modifient rien.

## 8. Série au quart d'heure (`ConsumptionSeries`)

Alimente le comparateur de tarifs. À chaque trame valide :

1. `dt` = temps depuis la trame valide précédente (≤ 0 ignoré ; > 1 h ramené à 1 h) ;
2. l'intervalle est **découpé aux frontières de quart d'heure** (00, 15, 30, 45) ; chaque tranche ajoute à son créneau : import, export, PV, maison (kWh = puissance × durée) ;
3. le prix d'achat et le prix de vente observés sont cumulés **pondérés par la durée** (moyenne temporelle par créneau).

Lecture : un créneau fournit `import_kwh`, `export_kwh`, prix d'achat moyen, prix de vente moyen (`None` si aucune valeur observée). Rétention : **62 jours** (purge à chaque trame). Persistance : écriture différée de **30 min** (`SERIES_SAVE_DELAY_S` = 1 800 s) ; au chargement, un store de schéma différent ou une ligne invalide est ignoré sans erreur ; `last_valid_ts = None`.

## 9. Capteurs exposés

- Maison : consommation, prélèvement, coût réseau, coût net, taux d'autonomie (jour).
- PV : production, autoconsommé, taux d'autoconsommation, réinjection, revenu, coût, solde, gain solaire estimé (jour).
- Ventilation : dynamique (import, export, coûts, net), HP, HC (jour).
- Appareils : énergie, part solaire, part réseau, coût, HP/HC, tarif actuel.
- Économies FoxCat : jour, mois, année.

## 10. Paramètres

Aucun réglage utilisateur n'influence le calcul du ledger. Constantes : intégration maximale 3 600 s ; sauvegarde 300 s ; série : créneau 900 s, rétention 62 jours.

## 11. Couverture par les tests

`tests/test_configuration.py` exerce `EnergyAccounting` sur deux cas (une réinjection à valeur négative ne modifie pas les kWh importés ; une machine CVC est comptabilisée séparément) ; `tests/test_tariff_comparison.py` couvre la série au quart d'heure (découpage aux frontières, prix pondérés, purge, persistance). **Non couverts** : la ventilation HP/HC et dynamique, les économies FoxCat (`foxcat_*`), le rollover de minuit pour les quatre seaux, l'intégration avec trou de mesure supérieur à 1 h.
