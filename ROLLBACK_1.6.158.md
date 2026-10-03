# FoxCat Energy 1.6.158 — Rollback

## Repli fonctionnel immédiat

Si l'arbitrage dynamique présente un comportement inattendu :

1. désactiver `Prédictif prix dynamique` pour revenir au comportement dynamique standard ;
2. conserver la règle de sécurité : une réinjection rémunératrice continue de libérer le PRI à 100 % ;
3. si nécessaire, repasser temporairement en régime HP/HC.

## Rollback logiciel

Restaurer l'archive 1.6.157 puis redémarrer Home Assistant.

Attention : 1.6.158 ajoute des champs Accounting mais conserve les anciens champs. Le retour 1.6.157 ignore simplement les nouveaux champs persistés.
