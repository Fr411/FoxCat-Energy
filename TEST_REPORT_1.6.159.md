# FoxCat Energy 1.6.159 — Rapport de tests de construction

## Tests passés

- compilation Python complète : OK ;
- parsing YAML dashboard officiel : OK ;
- parsing YAML dashboard client 1.6.159 : OK ;
- Accounting : import et export restent indépendants : OK ;
- Accounting : prix achat négatif reste signé : OK ;
- Accounting : export ne réduit pas le compteur import : OK ;
- Accounting : ventilation Dynamic / HP / HC : OK ;
- Scheduler inactif hors mode Dynamique : OK ;
- Scheduler : seuil favorable autorise un nouveau départ dans une plage utilisateur : OK ;
- Scheduler : durée ML prioritaire : OK ;
- Scheduler : refus si le cycle complet ne tient pas avant la fin de plage : OK ;
- Scheduler : cycle protégé toujours autorisé/prioritaire : OK ;
- inventaire AST : **349 -> 377**, **0 suppression** : OK ;
- hash des neuf fichiers sanctuarisés : identiques : OK.

## Validation terrain requise

La validation finale doit être réalisée sur Home Assistant réel pour :

- IDs d'entités effectivement créés après migration ;
- publication `today/tomorrow` Luminus ;
- comportement des prises LL/SL/LV ;
- consigne Boiler et sécurité 68 °C ;
- affichage ApexCharts et cartes custom ;
- persistance des nouveaux buckets Accounting après redémarrage.
