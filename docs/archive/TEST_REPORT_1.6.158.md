# FoxCat Energy 1.6.158 — Rapport de tests hors Home Assistant

Tests exécutés dans l'environnement de construction :

- compilation Python de tous les fichiers : OK ;
- parsing JSON `manifest.json`, `strings.json`, `translations/fr.json` : OK ;
- parseur Luminus Dynamic `all_in` : OK ;
- parseur Luminus Dynamic `injection` : OK ;
- Accounting export rémunérateur : revenu déduit du coût net : OK ;
- Accounting export coûteux : coût ajouté au coût net : OK ;
- PRI export rémunérateur en Dynamique avec prédictif OFF : 100 % : OK ;
- PRI export rémunérateur en HP/HC avec prédictif OFF : 100 % : OK ;
- calcul position/rang/tendance courbe Dynamic : OK ;
- moteur Dynamic utilise la valeur de réinjection normalisée et non le signe brut fournisseur : OK ;
- inventaire AST : 348 -> 349 fonctions, 0 suppression : OK.

La validation finale des entités, listeners Home Assistant, commandes RRCR et dashboards doit être faite sur l'instance réelle avant déploiement définitif.
