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
Batterie 10 kWh, 5 kW, rendements 95 %, SoC min 10 %, réserve 20 %. VE 80 kWh, 7,4 kW, rendement 90 %, SoC initial 50 %, cible semaine 80 %.
Horizon 48 pas, marge d'arbitrage 0,02 €/kWh. Rentabilité : 10 ans, taux 4 %, période observée >= 7 jours.

## Planification
- Le VE est simulé branché en semaine de 19:00 à 07:00, avec une cible minimale de 80 % au départ ; il est considéré absent entre 07:00 et 19:00.
- Le week-end, le VE reste présent et peut absorber le surplus solaire, jusqu'à sa capacité.
- L'arbitrage réseau virtuel compare le prix d'achat au prix de revente/évitement futur connu et retranche le coût d'usure configuré. En l'absence de prix futurs exploitables, aucune transaction n'est simulée.
- L'export batterie est réservé aux tarifs dynamiques : un pic courant doit dépasser les prix d'export futurs connus et le coût d'usure.

## Limitations
- Le shadow suppose que les mesures réelles ne contiennent pas d'effet de batterie/VE virtuels (une éventuelle batterie réelle n'est pas déduite).
- Aucun V2G : le VE ne fait que charger ; le planificateur est glouton (non optimal).
- La décharge batterie vers le réseau est une décision simulée uniquement et n'émet aucune commande matérielle.
- Le V2H matériel est une orchestration distincte, désactivée par défaut. Elle nécessite un switch, un capteur SoC réel et une configuration explicite; le seuil de réserve bloque toute décharge. Au déclenchement V2H, la chauffe de confort du boiler est suspendue.
- Le délestage à 90 % du disjoncteur ne s'active que lorsque le module haute consommation est autorisé. Les scénarios de prix développeur ne modifient jamais les prix live ni les commandes.
