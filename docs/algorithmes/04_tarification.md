# 04 · Tarification : prix actif, régime, comparateur, coûts réseau

> Sources : `domain/tariff/` (`tariff_model.py`, `tariff.py`, `tariff_prices.py`, `models.py`, `valuation.py`, `compare.py`, `grid_costs.py`, `legacy.py`, `templates.py`), `runtime/coordinator.py` (`prices`, `_tariff_comparison`, `_grid_costs_view`, `async_set_setting`), `runtime/migration.py`.
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

## 1. Deux axes, le reste est dérivé

L'utilisateur ne choisit que deux choses : le **contrat** (`price_source`) et la **structure du réseau** (`tariff_structure`). Tout le reste est calculé par `coherent_tariff_keys` :

| `price_source` | Sens |
|---|---|
| `Contractuelle / fixe` | prix saisis à la main |
| `Variable via entités Home Assistant` | prix lus depuis des capteurs |
| `Intégration externe` | ancien mode (traité comme dynamique) |
| `Dynamique Day-Ahead` | courbe horaire / quart d'heure |

| Structure | `tariff_structure` | `distribution_profile` | `dynamic_structure` | `tariff_regime` si non dynamique |
|---|---|---|---|---|
| mono | `Simple` | `Simple` | `Simple` | `Mono-horaire` |
| bi-horaire | `Bi-horaire` | `Bi-horaire (jour / nuit)` | `Bi-horaire` | `Bi-horaire (HP/HC)` |
| Impact | `Impact` | `Impact` | `Impact (Capacitaire)` | `Mono-horaire` |

Un contrat dynamique (ou intégration externe) donne `tariff_regime = Dynamique` et `tariff_family = dynamique` ; sinon `tariff_family = hphc`.

**Qui écrit ces clés** : l'assistant d'installation, l'écran « Contrat et réseau » et les cinq listes de l'appareil Tarification (Source du prix, Structure tarifaire, Régime Tarifaire, Profil distribution Belgique, Structure (Si Dynamique)). Dans le coordinateur, tout changement de l'une de ces cinq clés passe par `tariff_updates_for` : la liste modifie un axe, les autres clés sont réécrites. Le « Régime Tarifaire » *Dynamique* n'a d'effet de contrat que s'il n'est pas déjà dynamique ; *Mono* ou *Bi* ramène un contrat dynamique à `Variable via entités`, et **Mono remet la structure à Simple**. Un changement de régime déclenche `reset_core`.

### 1.1 Lecture des dimensions (`tariff_dimensions`)

```text
source    = price_source                          (défaut : Variable via entités)
structure = tariff_structure                      (défaut : Bi-horaire)
si le contrat est dynamique : structure = correspondance de dynamic_structure (Simple / Bi-horaire / Impact(Capacitaire)),
                              sinon la valeur de tariff_structure
profil    = distribution_profile, sinon déduit des anciennes clés (Impact > Bi-horaire > Simple)
politique = network_policy                        (défaut : Compensation)
```

### 1.2 Régime de compatibilité (`compatibility_tariff_regime`)

`Dynamique` si le contrat est dynamique ; sinon `Bi-horaire (HP/HC)` si la structure est bi-horaire ; sinon `Mono-horaire` (Impact compris).

## 2. Périodes (`tariff.py`)

Toutes les plages sont en **heure locale** et se lisent dans les réglages ; une plage qui franchit minuit est acceptée ; `début = fin` signifie « jamais ».

| Réglage | Défaut |
|---|---|
| `tariff_hp_start_1` / `end_1` | 07:00 → 11:00 |
| `tariff_hp_start_2` / `end_2` | 17:00 → 22:00 |
| `impact_peak_start` / `end` | 17:00 → 22:00 |
| `impact_eco_start_1` / `end_1` | 01:00 → 07:00 |
| `impact_eco_start_2` / `end_2` | 11:00 → 17:00 |

- `tariff_period` : `HP` dans une plage HP, sinon `HC` (**sans distinction de jour de semaine ni de week-end**).
- `distribution_period` selon le profil : bi-horaire → `HP`/`HC` ; Impact → `PIC` (plage de pointe), sinon `ECO` (deux plages), sinon `MEDIUM` ; simple → `ALL`.
- `is_offpeak_day` / `is_offpeak_night` découpent la HC en jour (11:00–17:00) et nuit (22:00–07:00).
- Les frontières de ces plages déclenchent `reset_core` (nouvelle acquisition) via un minuteur par frontière.

## 3. Prix d'achat actif (`prices()`, l. 1694)

### 3.1 Lecture des prix

| Prix | Source |
|---|---|
| `cur` | capteur « prix actuel » ou, à défaut, capteur de prix mono |
| `nxt` | capteur « prix suivant » |
| `inj` | capteur « prix de réinjection » |
| `hp`, `hc` | capteurs HP / HC ; **remplacés par les prix saisis** si le contrat est « Contractuelle / fixe » |

Un capteur illisible vaut `None`.

### 3.2 Prix final (`final_client_price`)

```text
si price_is_all_in :                      prix = prix lu                       (rien n'est ajouté)
sinon :
    si price_curve_is_final = faux :      prix += composante réseau + taxes + contrat      (€/kWh, défaut 0)
    période de distribution à l'instant :
        PIC / MEDIUM / ECO                prix += complément Impact correspondant
        HP / HC                           prix += tariff_tou_hp_adder ou tariff_tou_hc_adder
```

Les compléments valent 0 par défaut (champ −1 à 2 €/kWh). `price_curve_is_final` vaut vrai par défaut : la courbe lue est considérée finale.

### 3.3 Prix actif, suivant, étiquettes

| Cas | `active_buy` | `next_buy` | étiquette |
|---|---|---|---|
| dynamique | `cur` | `nxt` (évalué à `now + 1 h`) | `DYNAMIQUE` / `SUIVANT` |
| bi-horaire (non dynamique) | `hp` si HP, sinon `hc` | l'autre | `HP` ou `HC` |
| mono / Impact (non dynamique) | prix mono saisi (contrat fixe) ou `cur` | `nxt` ou `active` | `SIMPLE` |

`hp` et `hc` sont passés dans `final_client_price` **à l'instant courant** : chacun reçoit le complément de la période *actuelle* et non de sa propre période (A-14). Le prix actif est correct ; `hp_price`, `hc_price` et `next_buy` sont décalés quand les compléments HP et HC diffèrent.

### 3.4 Valeur de la réinjection (`export_value`)

| Politique réseau | Valeur |
|---|---|
| Injection non valorisée, Zéro injection | `0` |
| Injection tarifée, Compensation | prix dynamique de réinjection (contrat dynamique) ou prix fixe saisi (défaut 0) |

### 3.5 Prix négatif, référence, statut

- `negative_purchase` : `active_buy < 0`.
- `reference_buy` (prix « sans FoxCat ») : moyenne du jour avec compléments (dynamique), ou prix HP (bi-horaire non dynamique), sinon aucune.
- `status` (`price_status`) :

```text
prix actuel inconnu           → INDISPONIBLE
prix < 0                      → NÉGATIF
min/max du jour inconnus ou max ≤ min :
    moyenne inconnue → NORMAL ; prix < moyenne → BAS ; prix > moyenne → ÉLEVÉ ; sinon NORMAL
sinon position = (prix − min) ÷ (max − min) :
    ≤ 0,20 → TRÈS BAS ; ≤ 0,45 → BAS ; ≥ 0,80 → TRÈS ÉLEVÉ ; ≥ 0,60 → ÉLEVÉ ; sinon NORMAL
```

Le tableau de bord traduit « BAS / TRÈS BAS / NÉGATIF » en statut avantageux, « ÉLEVÉ / TRÈS ÉLEVÉ » en statut cher.

## 4. Modèle de tarif et valorisation (comparateur)

### 4.1 Le modèle (`models.py`)

Un `Tariff` est un ensemble de composantes :

| Composante | Options |
|---|---|
| énergie | `fixed` (un prix) ; `periods` (plages avec prix, prix hors plage = `energy_price`) ; `observed` (prix réellement lu à chaque créneau) |
| réseau | plages de compléments (€/kWh), complément « hors plages » `network_default`, complément plat `adder_flat` ; **ignorés si `all_in`** |
| réinjection | `none`, `fixed` (prix) ou `observed` (prix de vente observé, 0 s'il manque) |
| frais fixes | €/an |
| capacitaire | `none`, `flat` (forfait/an), `peak_monthly` (pointe mensuelle × €/kW/an ÷ 12, minimum facturé) |

Validation stricte : identifiant et nom non vides, nombres finis, heures valides (`HH:MM`, `24:00` accepté seul), jours 0–6. Les identifiants **`active`** et **`contract`** sont réservés (un tarif utilisateur de même identifiant est ignoré).

### 4.2 Les créneaux

La valorisation travaille sur des **créneaux d'un quart d'heure** (`Slot` : kWh importés, kWh exportés, prix d'achat et de vente observés). Leur construction est décrite dans `06_comptabilite.md`.

### 4.3 `value_series` (une fenêtre, un tarif)

Pour chaque créneau :

```text
import = max(import_kwh, 0) ; export = max(export_kwh, 0)
prix énergie : fixed → energy_price ; periods → prix de la 1ère plage qui contient l'instant, sinon energy_price ;
               observed → prix d'achat du créneau (inconnu : l'import est compté « sans prix », 0 €)
énergie      += import × prix énergie
réseau       += import × (0 si all_in, sinon complément de la 1ère plage / network_default + adder_flat)
réinjection  += export × (fixed : injection_price ; observed : prix de vente ou 0 ; none : 0)
```

Puis, sur la fenêtre :

```text
frais fixes  = frais_fixes_an × (nb créneaux × 0,25 h ÷ 8 760 h)
prosumer     = redevance_prosumer_an × (nb créneaux × 0,25 h ÷ 8 760 h)
capacitaire  = coût mensuel × min(part de la fenêtre dans le mois, 1)
     part = nb créneaux × 0,25 h ÷ heures du mois
     flat         → forfait_an ÷ 12
     peak_monthly → max(pointe du mois, minimum kW) × €/kW/an ÷ 12
     pointe       = max sur le mois de (kWh importés du quart d'heure ÷ 0,25 h)
total        = énergie + réseau + frais fixes + capacitaire + prosumer − réinjection
```

Le capacitaire **saisi pour l'installation** (menu Coûts réseau) l'emporte sur celui du tarif. Pour un mois en cours, c'est une estimation « à ce jour » fondée sur la pointe déjà observée.

### 4.4 `compare_tariffs`

Valorise chaque tarif, trie par total croissant, désigne le moins cher et calcule `ecart_vs_reference` = total du tarif − total du tarif de référence (le tarif **actuel**). Un écart négatif signifie « moins cher que l'actuel ». Chaque tarif indique aussi si sa réinjection est valorisée.

### 4.5 Quels tarifs sont comparés (`_comparison_tariffs`)

1. **Tarif actuel** (`active`) : prix d'achat et de réinjection **observés**, `all_in` → ce que FoxCat a réellement appliqué.
2. **Contrat saisi** (`contract`) : reconstruit depuis les réglages **seulement** pour la source « Contractuelle / fixe » (`tariff_from_settings`) :
   - bi-horaire : énergie par plages (HP sur les deux plages HP, HC hors plage), compléments HP / HC ;
   - Impact : prix simple, compléments par période ECO / PIC et MEDIUM hors plages ;
   - mono : prix simple ;
   - réinjection fixe si le prix saisi est non nul.
   Ce tarif **ignore** `price_is_all_in` et les composantes réseau/taxes/contrat (A-15).
3. **Tarifs de l'utilisateur** (JSON des options, modèles Wallonie `wal_mono`, `wal_bi_2026`, `wal_impact`). Un JSON invalide est ignoré avec un avertissement dans le journal.

Régions et modèles préchargés : Wallonie → les trois ; Flandre et Bruxelles → mono seulement ; « Autre » → aucun.

### 4.6 Fenêtres et cache

`today` = de minuit à maintenant ; `month` = du 1ᵉʳ du mois à maintenant. Le résultat est mis en **cache** (durée `COMPARISON_REFRESH_S`) pour ne pas recalculer un mois de créneaux à chaque trame. Toute exception du comparateur est capturée (`error: true`) et ne casse jamais la trame.

## 5. Coûts réseau (`grid_costs.py`)

Réglages saisis par l'installateur : type capacitaire (`none` / `flat` / `peak_monthly`), forfait annuel, €/kW/an, minimum kW, redevance prosumer annuelle. Lecture tolérante : valeur invalide ou négative → 0, type inconnu → aucun.

Propositions de départ à l'installation (guide des tarifs 2026) : **Flandre** pointe mensuelle à 55 €/kW/an (minimum 2,5 kW) ; **Bruxelles** forfait 47 €/an.

Capteur « Coûts réseau • Ce mois » = capacitaire + prosumer du tarif actuel sur le mois ; attributs : pointe FoxCat, pointe de l'intégration de prix (contrôle), écart de pointe, valeurs de contrôle de l'intégration (jamais additionnées).

## 6. Paramètres de cette page

| Réglage | Défaut | Rôle |
|---|---|---|
| `price_source`, `tariff_structure`, `network_policy` | variable / bi-horaire / Compensation | les axes |
| `price_is_all_in` | faux | ne rien ajouter au prix lu |
| `price_curve_is_final` | vrai | la courbe lue est finale |
| `tariff_network_component_eur_kwh`, `…_tax_…`, `…_contract_…` | 0 | compléments si la courbe n'est pas finale |
| `tariff_tou_hp_adder_eur_kwh` / `…_hc_…` | 0 | compléments de distribution HP / HC |
| `impact_eco_adder…` / `impact_medium_adder…` / `impact_peak_adder…` | 0 | compléments Impact |
| `tariff_simple_fixed_price_eur_kwh`, `tariff_hp_price_eur_kwh`, `tariff_hc_price_eur_kwh` | 0,30 / 0,35 / 0,25 | prix saisis |
| `tariff_fixed_injection_eur_kwh` | 0 | prix de réinjection fixe |

## 7. Couverture par les tests

`tests/test_tariff_comparison.py` (valorisation, comparateur, grid costs), `tests/test_tariff_configurator_flow.py` (assistant et options), `tests/test_tariff_selectors_sync.py` (cohérence listes ↔ menu), `tests/test_configuration.py` (migrations, dimensions). **Non couverts** : `prices()` et `final_client_price` (compléments HP/HC par période), `tariff_from_settings` avec `price_is_all_in`, `price_status`.
