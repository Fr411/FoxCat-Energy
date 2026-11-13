# Plan de modification : configurateur de tarifs et comparateur

Complète `PROPOSITION_STANDARDISATION_TARIFS.md` (le « pourquoi »). Ce document est le « comment » : fichiers touchés, ordre, tests, critères de fin.

## 0. Points de départ vérifiés

- **Le coordinateur actif est `custom_components/foxcat_energy/runtime/coordinator.py`** (importé par `__init__.py`). Le fichier `coordinator.py` à la racine du composant n'est importé par aucun module ; il diffère du fichier actif sur environ 400 lignes. Les numéros de ligne donnés plus haut dans la conversation pour `coordinator.py` viennent de ce fichier inactif ; la logique du bilan maison (`house = pv + import - export`) est la même dans le fichier actif (`runtime/coordinator.py:1339`).
- Il existe aussi des copies à la racine du dépôt (`tariff_model.py`, `flexible_load_planner.py`, `machine_learning.py`, `patch_coordinator.py`). `tariff_model.py` diffère déjà de `domain/tariff/tariff_model.py`.
- **Base de tests :** `python3 -m unittest discover -s tests` → 225 tests, OK, 61 ignorés (probablement ceux qui exigent Home Assistant, absent de cet environnement). Les changements de `config_flow` ne pourront donc pas être entièrement testés ici.
- Persistance : `Store(hass, 1, ...)` dans le coordinateur ; le ledger (`domain/accounting/manager.py`) est sauvegardé par `dump()` / `restore()` (schéma 2).
- Version actuelle : 1.7.6 (`manifest.json`).

## Phase 0 : nettoyage (PR séparée, optionnelle mais conseillée)

Objectif : une seule source de vérité avant d'ajouter du code.

| Tâche | Détail |
|---|---|
| Confirmer que `coordinator.py` (racine du composant) est inutilisé | recherche des imports, lancement des tests |
| Le retirer, ou le marquer obsolète | à décider avec toi (suppression = irréversible hors git) |
| Traiter les copies à la racine du dépôt | idem |

**Fin :** tests identiques (225 OK), aucune référence restante.

## Phase 1 : modèle de tarif et valorisation (aucun changement visible)

Nouveau paquet `domain/tariff/`.

| Fichier | Contenu |
|---|---|
| `models.py` | dataclasses `Tariff`, `EnergyComponent`, `Period`, `CapacityTerm`, `FixedFee`, `InjectionRule` ; champ `all_in: bool` |
| `valuation.py` | `value_series(series, tariff, spot_history) -> CostBreakdown` : fonction pure, sans Home Assistant |
| `templates.py` | modèles prédéfinis (Wallonie mono, bi-horaire 2026, Impact ; Dynamique ; Flandre capacitaire ; Bruxelles forfait) |
| `legacy.py` | conversion des réglages actuels (`price_source`, `tariff_structure`, `distribution_profile`, plages, compléments) vers un `Tariff` |

Règles à coder et tester :
- Une composante `all_in` désactive les compléments réseau, taxes et marge du même tarif (corrige le double comptage de `final_client_price`).
- Plages sur minuit (22h–07h) et plages multiples (HP 07–11 + 17–22, ECO 11–17).
- Capacitaire : `max(moyenne mensuelle des pointes 1/4 h, 2,5 kW)` ; forfait selon la puissance.

**Tests** (`tests/test_tariff_model.py`, `tests/test_tariff_valuation.py`) : une série synthétique d'une journée, un résultat attendu chiffré par modèle, et un test d'équivalence avec `final_client_price` pour les réglages actuels (aucune régression de prix).

**Fin :** `final_client_price` et `valuation` donnent le même prix sur tous les cas existants.

## Phase 2 : série par quart d'heure et historique spot

| Fichier | Changement |
|---|---|
| `domain/accounting/series.py` (nouveau) | tampon quart d'heure : import, export, PV, maison (kWh) + prix spot du créneau |
| `domain/accounting/manager.py` | `process()` alimente la série sans toucher aux buckets actuels |
| `runtime/coordinator.py` | sauvegarde / restauration de la série (nouveau magasin ou clé dédiée) ; rétention 13 mois ; purge |
| `runtime/migration.py` | migration du schéma, `schema` 2 → 3, lecture tolérante des anciennes sauvegardes |

Contraintes : ne jamais intégrer le temps d'arrêt de Home Assistant (comportement actuel de `restore()`), taille bornée, écriture groupée (le coordinateur sauvegarde déjà toutes les 5 minutes).

**Tests :** intégration sur une trame simulée, rollover de quart d'heure, trou de données, restauration d'une sauvegarde ancienne.

**Fin :** les totaux jour/mois/année existants sont identiques à avant (test de non-régression sur `manager.py`).

## Phase 3 : configuration

| Fichier | Changement |
|---|---|
| `config_flow.py` | installation en trois questions (contrat, réseau, région) ; suppression des entités Luminus préremplies (`config_flow.py` et `runtime/registry.py`) ; prix HP/HC demandés seulement si le contrat est bi-horaire |
| `config_flow.py` (`FoxCatEnergyOptionsFlow`) | menu : ajouter / éditer / supprimer un tarif, ajouter / éditer / supprimer une plage, choisir le tarif actif, importer / exporter en JSON |
| `strings.json`, `translations/fr.json` | libellés des nouvelles étapes |
| `runtime/profiles.py`, `runtime/migration.py` | validation et migration vers un premier tarif « actif » |
| `select.py` | les entités `select` actuelles restent lisibles pendant une version de transition |

Le flux d'options existant est transactionnel (changements en mémoire, validation à la fin) ; les nouvelles étapes doivent respecter ce principe.

**Tests :** étapes du flux (les tests qui exigent Home Assistant sont ignorés ici, donc à valider dans une vraie instance), migration d'une configuration existante vers le nouveau modèle, import / export JSON aller-retour.

**Fin :** une installation existante démarre sans changement de comportement ; une nouvelle installation peut être configurée sans aucune liste figée.

## Phase 4 : sources de prix et publication

| Fichier | Changement |
|---|---|
| `runtime/coordinator.py` (`prices()`, `_economic_import_points`) | lecture du tarif actif ; composante `all_in` lue depuis l'entité choisie |
| Configurateur | détection des entités de l'intégration de prix tout compris ; association aux champs `price_*` existants |
| `runtime/coordinator.py` | surveillance du signal de publication (Nord Pool `prix_de_demain_disponible`, `derniere_mise_a_jour`) → appel du service `refresh` de l'intégration de prix → attente de `tomorrow_prices_available` → relecture et replanification |
| `domain/pricing/economic_optimizer.py` | ajouter si besoin les clés d'attributs manquantes (`_SERIES_KEYS`) |

À confirmer avant cette phase (sur l'installation réelle) : attributs de `current_price` et `injection_price`, nom du domaine de service `refresh`, comportement à plusieurs instances.

**Tests :** lecture d'une courbe au format `{start, energy, network, taxes, all_in}` ; signal de publication simulé ; retard de publication (le tick horaire reste le filet de sécurité).

**Fin :** pas de double comptage avec une source `all_in` (test dédié) ; la courbe du lendemain est relue peu après le signal.

## Phase 5 : comparateur

| Fichier | Changement |
|---|---|
| `domain/tariff/compare.py` (nouveau) | applique N tarifs à la série et renvoie coût par composante et écart au tarif actif |
| `sensor.py`, `runtime/registry.py` | capteurs : coût par tarif (jour / mois / année) et écart |
| `dashboard/` | carte de comparaison (nouvelle version de dashboard, comme les fichiers `versions/`) |

À afficher : « à comportement constant », composantes comparées, tarif actif.

**Fin :** pour la période, la somme des composantes du tarif actif égale le coût du ledger (test de cohérence).

## Phase 6 : coûts réseau manquants

| Tâche | Détail |
|---|---|
| Capacitaire flamand | pointe 1/4 h mensuelle mémorisée, coût mensuel estimé ; ou lecture de `capacity_cost` de l'intégration de prix |
| Forfait Bruxelles | selon la puissance (< ou > 13 kVA) |
| Redevance prosumer wallonne | forfaitaire (kWe de l'onduleur) ou proportionnelle (compteur intelligent) ; ou lecture de `prosumer_cost` |

Valeurs chiffrées toujours éditables.

## Ordre, versions et PR

| Phase | Version | Risque | Visible pour l'utilisateur |
|---|---|---|---|
| 0 | 1.7.7 | faible | non |
| 1 | 1.8.0 | faible | non |
| 2 | 1.8.0 | moyen (persistance) | non |
| 3 | 1.8.0 | élevé (configuration) | oui |
| 4 | 1.8.1 | moyen | oui |
| 5 | 1.8.2 | faible | oui |
| 6 | 1.8.3 | moyen | oui |

Une PR par phase, avec entrée dans `CHANGELOG.md` et `JOURNAL_VERSIONS.md`. Les phases 1 et 2 peuvent partir en parallèle ; la phase 3 dépend de la 1 ; la 5 dépend de la 2.

## Risques et parades

| Risque | Parade |
|---|---|
| Régression de prix sur les installations existantes | test d'équivalence de la phase 1, migration sans changement de comportement |
| Sauvegarde corrompue ou volumineuse | schéma versionné, rétention bornée, lecture tolérante |
| Flux de configuration non testable ici (61 tests ignorés) | essai sur une instance Home Assistant avant chaque version |
| Double source de coût (ledger et intégration de prix) | afficher la source sur chaque capteur |
| Tarifs belges qui changent chaque année | modèles versionnés par millésime, valeurs éditables |
| Fichier `coordinator.py` inactif qui induit en erreur | phase 0 |

## Décisions attendues de ta part

1. Phase 0 : supprimer le `coordinator.py` inactif et les copies à la racine, ou les garder ?
2. Valider la liste des composantes d'un tarif (section 3.1 de la proposition).
3. Les plages Flandre et Bruxelles : peux-tu fournir celles de ton gestionnaire de réseau ?
4. Dans quelle région es-tu, avec quel contrat ? Cela fixe la première version de modèles testée en réel.
