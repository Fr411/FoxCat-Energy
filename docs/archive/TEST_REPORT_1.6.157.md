# FoxCat Energy 1.6.157 — Rapport de tests

## Environnement

Validation statique et Python pure effectuée hors runtime Home Assistant. Home Assistant n'est pas installé dans l'environnement de build ; les essais de Config Flow, entity registry et services HA doivent donc être finalisés sur l'instance de staging selon `VALIDATION_PLAN_1.6.157.md`.

## Résultats

- Compilation de tous les fichiers Python : **PASS**
- Parsing de tous les JSON : **PASS**
- Audit fonctions : **342 -> 348**, +6, **0 supprimée**
- 300 cas économiques HP/HC comparés à 1.6.156 : **PASS 300/300**
- 500 cas InverterCore non dynamiques comparés à 1.6.156 : **PASS 500/500**
- Bandes dynamiques BAS / MEDIAN / HAUT : **PASS**
- MEDIAN / HAUT ne peuvent pas activer une réservation de charge réseau : **PASS**
- Kill-switch prédictif -> repli standard : **PASS**
- Machine protégée -> `CYCLE_EN_COURS`, non interrompue : **PASS**
- Export dynamique signé positif -> PRI 100 % : **PASS**
- Export dynamique signé négatif -> bridage prédictif : **PASS**
- Compensation -> PRI 100 % : **PASS**
- `engine/pri.py` règle signée : **PASS**
- `engine/modes/dynamic.py` identique bit pour bit à 1.6.156 : **PASS**

## Limitation de validation

Les points suivants nécessitent un test Home Assistant réel :

- création/renommage effectif des nouveaux entity_id suggérés ;
- affichage Config Flow et traductions ;
- rechargement de ConfigEntry après modification Boiler ;
- services physiques Boiler/RRCR ;
- comportement avec le fournisseur de prix Day-Ahead réel ;
- comportement après redémarrage HA.
