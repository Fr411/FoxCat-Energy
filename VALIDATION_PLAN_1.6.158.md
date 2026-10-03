# FoxCat Energy 1.6.158 — Plan de validation Home Assistant

## 1. Sources tarifaires

1. Sélectionner régime **Dynamique**.
2. Vérifier que `Prix d'achat actif` suit Luminus Dynamic.
3. Vérifier que `Position sur la courbe dynamique`, `Rang prix dynamique` et `Tendance courbe dynamique` sont renseignés.
4. Vérifier que `points_prix` de `Décision économique EMS` dépasse 6 lorsque `today/tomorrow` sont disponibles.
5. Passer en **Bi-horaire HP/HC** et vérifier que `Prix d'achat actif` suit uniquement les capteurs ComfyFlex HP/HC.

## 2. Réinjection positive

1. Politique = **Injection tarifée**.
2. Fournir une valeur économique de réinjection > 0.
3. Tester en Dynamique puis HP/HC.
4. Couper `switch.foxcat_predictive_pricing_enabled`.
5. Dans tous les cas, vérifier cible PRI = **100 %**.

## 3. Réinjection négative

1. Fournir une valeur de réinjection < 0.
2. Vérifier que le PRI peut rechercher la quasi-zéro injection.
3. Vérifier que l'Accounting augmente `Coût réinjection aujourd'hui`.
4. Vérifier : `coût net = achat + coût export - revenu export`.

## 4. Accounting rémunérateur

1. Importer et exporter au cours de la même journée.
2. Vérifier `Coût réseau aujourd'hui` = coût brut d'achat.
3. Vérifier `Revenu réinjection aujourd'hui` > 0.
4. Vérifier `Coût net aujourd'hui` inférieur au coût brut du montant du revenu d'export.

## 5. Courbe Dynamic

1. Observer un prix proche du minimum : position % faible / rang bas.
2. Observer le passage vers un pic : tendance HAUSSE puis position plus haute.
3. Vérifier que la bande BAS/MEDIAN/HAUT est calculée sur la courbe Luminus Dynamic `all_in` et non sur ComfyFlex.

## 6. Charges flexibles

Tester trois cas :

- prix haut + export coûteux + solaire disponible : une charge peut être autorisée si son coût marginal est meilleur que le futur ;
- prix haut + export très rémunérateur : la charge doit pouvoir être reportée si vendre maintenant et acheter plus tard est meilleur ;
- cycle machine déjà protégé : jamais interrompu.

## 7. Boiler

- sécurité 68 °C inchangée ;
- confort minimum inchangé ;
- comparer un créneau futur bon marché avec un créneau actuel solaire + réseau ;
- vérifier que FoxCat choisit le coût marginal réellement le plus favorable.

## 8. Dashboard

Vérifier que toutes les cartes utilisent :

- `pricing.active_buy` pour le prix actif ;
- `pricing.next_buy` pour le prix suivant ;
- `pricing.net_today` pour le coût net ;
- Dynamic uniquement en mode Dynamique ;
- ComfyFlex uniquement en mode HP/HC.
