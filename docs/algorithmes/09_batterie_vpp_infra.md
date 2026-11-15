# 09 · Batterie et véhicule virtuels, VPP / V2H, IA solaire, profils, migration, dashboards

> Sources : `trading/virtual_assets/*`, `trading/vpp.py`, `runtime/coordinator.py` (`_evaluate_v2h`, `async_analyze_solar`, `_deterministic_solar_fallback`, `_solar_prompt`), `runtime/profiles.py`, `runtime/migration.py`, `dashboard/merge.py`, `dashboard/dashboard.py`, `dashboard/versions.py`.
> Les écarts `A-xx` sont détaillés dans [ANOMALIES.md](ANOMALIES.md).

# Partie A · Batterie et véhicule électrique virtuels (simulation)

## A1. Principe

Module **en lecture seule** : il simule ce qu'apporteraient une batterie domestique et un véhicule électrique, **sans jamais commander un appareil** et sans toucher au registre réel. Désactivé par défaut (`virtual_assets_enabled`). Le *mode shadow* (par défaut) fait tourner la simulation **en parallèle des mesures réelles** : les données réelles restent « mesurées », tout le reste est « simulé » ou « estimé ». Une valeur manquante n'est jamais fabriquée : le pas est ignoré (`missing_load_or_pv`).

## A2. Modèles physiques

**Batterie** (`VirtualBattery`) — énergie en kWh côté cellule, flux côté AC.

| Paramètre | Défaut |
|---|---|
| capacité | 10 kWh |
| puissance de charge / décharge | 5 / 5 kW |
| rendement de charge / décharge | 95 % / 95 % |
| SoC minimum / maximum / réserve | 10 % / 100 % / 20 % |
| coût d'usure | capex ÷ débit nominal si connus, sinon réglage `battery_degradation_cost_eur_kwh`, sinon 0 |

```text
charge max AC   = min(puissance × h, place restante ÷ rendement de charge)
décharge max AC = min(puissance × h, (SoC − plancher) × rendement de décharge)      plancher = SoC min (ou la réserve pour une décharge discrétionnaire)
```

**Véhicule** (`VirtualEV`) : charge seule (pas de V2G dans la simulation). Défauts : 80 kWh, 7,4 kW, rendement 90 %, SoC initial 50 %, réserve de mobilité 20 %. Une **session** donne la plage de présence (arrivée, départ), le SoC d'arrivée et le SoC cible au départ ; le besoin AC = énergie manquante ÷ rendement ; sans session branchée, aucune charge.

## A3. Planificateur à horizon glissant (`plan_and_apply`)

Pour chaque pas (15 min ou plus), le moteur replanifie sur une fenêtre de **48 pas** (`horizon_slots`) et décide du premier pas. Priorités, de la plus forte à la plus faible :

1. contraintes physiques (puissance, capacité, plancher de SoC) ;
2. besoin de départ du véhicule ;
3. surplus solaire (véhicule puis batterie) ;
4. réduction d'import (décharge jusqu'à la réserve) ;
5. arbitrage tarifaire (charge réseau seulement si le gain net dépasse la marge) ;
6. préservation de la réserve ;
7. minimisation de l'usure (coût d'usure déduit des gains).

Détail d'un pas (`net = PV − consommation`) :

- **Véhicule** : allocation choisie parmi les pas de la fenêtre : d'abord ceux à surplus solaire, puis les moins chers, puis ceux sans prix ; si le départ n'est pas imminent et qu'il y a du solaire, la charge du premier pas est limitée au surplus.
- **Surplus** (après le véhicule) : stocké dans la batterie, sauf si un **pic d'export** est confirmé.
- **Déficit** : la batterie se décharge si `prix d'import − usure > 0`, en gardant de l'énergie pour les pas futurs **plus chers** (`holdback`) et jamais sous la réserve.
- **Pic d'export** (si l'arbitrage d'export est permis, c'est-à-dire en dynamique) : `prix d'export > usure` et supérieur d'au moins la marge (0,02 €/kWh) au maximum des prix futurs.
- **Arbitrage réseau** (permis par défaut) : charge sur le réseau si un prix futur couvre `prix actuel ÷ (η_charge × η_décharge) + usure + marge`, sans pas moins cher à venir pour la décharge d'import ; un prix manquant interdit l'arbitrage.
- **Action rapportée** : `charge_battery_grid`, `discharge_battery_to_grid`, `discharge_battery`, `charge_battery_solar`, `charge_ev` ou `idle`, avec la liste des raisons.

## A4. Comptabilité simulée et rentabilité

- `SimulatedLedger` compare chaque pas au scénario **sans batterie** (`baseline_step`) : économie = coût de référence − coût simulé ; les pertes de conversion sont comptées.
- `analyze_profitability` : économie annualisée **linéairement** (période observée ≥ **7 jours**, sinon « donnée manquante »), puis ROI, retour sur investissement, VAN (taux 4 %, 10 ans par défaut), dégradation annuelle (0 si inconnue, signalé), sensibilité au coût de remplacement (×0,5, ×1, ×1,5). Chaque indicateur vaut `None` si une donnée manque.
- Qualité des données : « mesuré » / « estimé » / « simulé ».
- État persisté (`state_store`) avec contrôle de l'horloge : un instant non strictement croissant est refusé.

## A5. Alimentation depuis FoxCat

À chaque trame, `observe_snapshot` convertit l'instantané en créneau (consommation, PV, prix d'import et d'export) et les prévisions de prix en créneaux « estimés ». Le prix d'import est vérifié par `TariffAdapter` : prix « tout compris » ou prix de gros converti ; un prix refusé n'alimente aucune comptabilité (`PriceRefused`).

---

# Partie B · VPP et V2H (véhicule vers maison)

## B1. Arbitrage d'achat / revente (`evaluate_trade`)

```text
écart = meilleur prix de revente futur − prix d'achat actuel
batterie rentable = écart > usure batterie (€/kWh)        véhicule rentable = écart > usure véhicule
```

Résultat purement informatif (vue économique).

## B2. V2H physique (`evaluate_v2h` + `_evaluate_v2h`)

Fonction **opt-in**, distincte de la simulation. Elle exige : V2H activé, une **commande du chargeur** (switch), un mode ≠ Manuel et un snapshot valide.

**Signaux** :

| Signal | Condition |
|---|---|
| **Écrêtage** | le délestage est **armé** (délestage actif, protection activée, mode ≠ Manuel), l'option « V2H assiste l'écrêtage » est active, un calibre est connu, et la puissance comparée ≥ `calibre utile × seuil de déclenchement` |
| **Bouclier tarifaire** | le statut du prix vaut « TRÈS ÉLEVÉ » (position ≥ 80 % de la courbe du jour) |

**Verrous** : sans SoC lisible, commande bloquée ; SoC < réserve de mobilité (25 % par défaut, réglage `ev_v2h_min_soc_pct`) → bloqué.

**Puissance cible** :

```text
écrêtage : max(puissance comparée − calibre utile × cible V2H (80 %), 0)
bouclier : consommation maison
puis bornée par la puissance maximale V2H (5 000 W par défaut)
```

**Commande** : si actif, consigne de puissance (entité `number`, si elle diffère de ≥ 10 W) puis `switch.turn_on` ; sinon consigne 0 et `switch.turn_off` si le chargeur est allumé. Appels non bloquants ; une exception coupe l'état V2H. L'interverrouillage « `thermal_interlock` » arrête la chauffe de confort du boiler tant que le V2H est actif (voir 01).

**Limite** : `_evaluate_v2h` n'est appelée que depuis `_evaluate_high_load`, qui ne tourne que si la régulation est active ; couper la régulation pendant un V2H actif ne ramène pas le chargeur à l'arrêt (A-26).

---

# Partie C · IA solaire

## C1. Rôle

Module **consultatif** : il ne commande jamais un équipement. Son résultat (`SolarForecast`) sert de **fenêtre solaire** au planificateur Day-Ahead (voir 05) quand « arbitrage prévision solaire » est actif. Actif seulement si « Analyse prédictive IA » est activée.

## C2. Agent IA (si configuré)

Appelle `ai_task.generate_data` avec un prompt contenant : PV, maison, export, import, température du boiler, confort minimal, plages HP/HC, et les prévisions Forecast.Solar (maintenant, heure en cours, heure suivante, restant, pic aujourd'hui/demain). Réponse structurée : décision OUI/NON, début, fin, confiance (0–100), potentiel (Aucun…Fort), tendance (NOUVELLE, CONFIRMÉE, DÉCALÉE, DÉGRADÉE, ANNULÉE), justification (255 caractères). Tout champ hors valeurs permises : la réponse est **rejetée** et le repli est utilisé.

Déclenchement : sur demande (bouton) et à des heures planifiées (`async_track_time_change`).

## C3. Repli déterministe (`_deterministic_solar_fallback`)

```text
puissance = max des prévisions (maintenant, 1 h, heure suivante)
potentiel : ≥ seuil « fort » → Fort (confiance 85) ; ≥ « bon » → Bon (78) ; ≥ « possible » → Moyen (70) ; ≥ minimum → Faible (55) ; sinon Aucun (30)
fenêtre disponible = potentiel ∈ {Moyen, Bon, Fort} ET confiance ≥ solar_confidence_min_percent
début = heure du pic du jour (si disponible) ; fin = inconnue
```

> Le prompt envoyé à l'agent contient les plages **HC 22:00–07:00 et 11:00–17:00 / HP 07:00–11:00 et 17:00–22:00 écrites en dur**, quelle que soit la configuration (A-27).

---

# Partie D · Profils de réglages

Services `foxcat_energy.save_settings_profile`, `load_settings_profile`, `reset_settings`. Fichiers JSON `{ "settings": {...} }` dans `/config/foxcat_energy/profiles/` ; nom `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. L'écriture est **atomique** (fichier temporaire puis remplacement).

Validation (`validate_profile_settings`) : clés inconnues refusées ; nombres finis et dans les bornes de leur entité ; heures `HH:MM[:SS]` ; interrupteurs booléens ; mode ramené à son nom canonique ; politique réseau, source de prix, structure et régime restreints aux listes autorisées ; puis **cohérence tarifaire** : un régime Dynamique impose la source Day-Ahead, un régime HP/HC ou simple ramène un contrat dynamique à « variable » et fixe la structure, et le régime est recalculé à partir de la source et de la structure. À l'application, le coordinateur relâche l'onduleur, arrête le boiler si sa gestion est coupée, et réconcilie les machines.

# Partie E · Migration des réglages

`migrate_settings_v171` puis `v173` (appelées au chargement) :

| Ancien réglage | Résultat |
|---|---|
| mode Dynamique / « Prix dynamique » ou régime Dynamique | source Day-Ahead |
| mode Bihoraire / ECS solaire / HP/HC ou régime bi-horaire | structure bi-horaire |
| mode « Zéro injection » / « Réinjection refusée » | politique **Zéro injection** |
| mode « Réinjection autorisée » (sans politique) | politique **Injection tarifée** |
| autre | politique **Compensation** (défaut) |
| tout ancien mode | **Éco** (ou **Manuel** s'il l'était) ; l'ancien mode est conservé dans `legacy_mode_v160` |

Puis : source de prix, structure et politique invalides ramenées à une valeur valide (alias connus), régime recalculé (`compatibility_tariff_regime`), `dynamic_high_position_pct` initialisé à 70 % s'il manquait, interrupteurs `device_*_enabled` mis à vrai s'ils manquaient, version de modèle `1.7.5`.

# Partie F · Dashboards (versions, sauvegarde, fusion)

- **Versions** : fichiers `dashboard_v<version>.yaml` (tablette/PC) et `dashboard_mobile_v<version>.yaml` (mobile) avec leur manifeste ; les sélecteurs de version sont indépendants par variante.
- **Application** (`_apply`) : crée le dossier, **sauvegarde `.bak`** de l'existant, écrit le gabarit rendu et un fichier d'état ; un dashboard **personnalisé** n'est pas écrasé au démarrage.
- **Fusion à trois sources** (`merge_dashboard_text(base, utilisateur, dernier)`) : calcule les modifications ligne à ligne (`difflib`) de l'utilisateur et du nouveau gabarit par rapport à la base ; si deux modifications se **recouvrent** sans être identiques, la fusion est refusée (« aucun changement appliqué ») ; sinon, toutes les modifications du nouveau gabarit puis celles de l'utilisateur absentes du gabarit sont appliquées de la fin vers le début.
- **Restauration** : le bouton de restauration remet la version précédente depuis le `.bak`.

# Couverture par les tests

`tests/test_virtual_assets.py` (49 tests : modèles, planificateur, rentabilité, comptabilité simulée, shadow), `tests/test_vpp.py` (décisions VPP et V2H, comptabilité et apprentissage avec trous de télémétrie, planificateur et délestage), `tests/test_configuration.py` (profils, migrations, fusion de dashboards y compris un conflit). **Non couverts** : les **commandes** V2H de `_evaluate_v2h`, le prompt et la réponse de l'agent IA, l'application et la restauration d'un dashboard sur disque.
