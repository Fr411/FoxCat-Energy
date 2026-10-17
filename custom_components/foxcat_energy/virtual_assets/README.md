# Virtual Assets Core

Sous-système de simulation **en lecture seule et désactivé par défaut**
(`virtual_assets_enabled`) pour une batterie domestique et un VE. Il ne commande
**aucun** équipement physique (aucun appel de service HA). Les paramètres se
configurent dans FoxCat Energy → Batterie + VE; le dashboard expose leur
configuration, pas le SoC d'équipements physiques.

## Réutilisation
- Calendrier HP/HC : `engine.tariff.tariff_period` (AIESH : HP 07:00-11:00 et 17:00-22:00, HC sinon, identique tous les jours).
- Conversion gros → final : `tariff_model.final_client_price` ; courbes : `price_analyzer.analyze_price_curve`.
- Clés comptables : `accounting.manager.ZERO` (ledger séparé de `EnergyAccounting`, qui reste le seul ledger du réel).

## Qualité des données
`measured` (réel), `simulated` (calculé), `estimated` (prix futurs, annualisation), `missing`
(jamais inventé : pas d'arbitrage, pas de coût, compté dans `unpriced_slots`).

## Défauts
Batterie 10 kWh, 5 kW, rendements 95 %, SoC min 10 %, réserve 20 %. VE 50 kWh, 7,4 kW, 90 %, sans V2G.
Horizon 48 pas, marge d'arbitrage 0,02 €/kWh. Rentabilité : 10 ans, taux 4 %, période observée >= 7 jours.

## Limitations
- Le shadow suppose que les mesures réelles ne contiennent pas d'effet de batterie/VE virtuels (une éventuelle batterie réelle n'est pas déduite).
- Pas de V2G ni d'export batterie ; fenêtre VE limitée à l'horizon ; le planificateur est glouton (non optimal).
- La page Batterie + VE enregistre la configuration de simulation. Le flux de mesures HA
  n'est pas encore raccordé au simulateur : l'activation seule ne produit pas de télémétrie
  ni de pilotage.
- Hooks HA (`ha.py`) fournis mais non câblés dans `__init__.py` / `diagnostics.py` existants pour garder l'isolation.
