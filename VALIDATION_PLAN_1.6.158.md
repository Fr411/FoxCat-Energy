# FoxCat Energy 1.6.158 — Plan de validation Home Assistant

## 1. Sources tarifaires

### Dynamique

1. Sélectionner `Dynamique`.
2. Vérifier que `Prix d'achat actif` = Luminus Dynamic actuel.
3. Vérifier que `Prix d'achat suivant` = Luminus Dynamic H+1.
4. Vérifier que `Position sur la courbe dynamique` est disponible.
5. Vérifier que la décision expose au moins 6 points de courbe lorsque la table Luminus est disponible.

### HP/HC

1. Sélectionner `Bi-horaire HP/HC`.
2. En HP, vérifier que `Prix d'achat actif` = ComfyFlex HP.
3. En HC, vérifier que `Prix d'achat actif` = ComfyFlex HC.
4. Vérifier qu'aucun prix Luminus Dynamic n'est affiché comme prix actif.

## 2. Réinjection

### Rémunératrice

1. Régime Dynamique.
2. Observer une valeur Luminus d'injection > 0.
3. Vérifier `Valeur économique de la réinjection` > 0.
4. Vérifier cible PRI = 100 %, même si `Prédictif prix dynamique` est OFF.

### Coûteuse

1. Observer une valeur Luminus d'injection < 0.
2. Vérifier `Valeur économique de la réinjection` < 0.
3. Vérifier que le coût de réinjection augmente `Coût net aujourd'hui`.

## 3. Accounting

Sur une fenêtre connue :

- comparer `Coût réseau aujourd'hui` ;
- comparer `Revenu de réinjection aujourd'hui` ;
- comparer `Coût de réinjection aujourd'hui` ;
- vérifier : `net = achat + coût export - revenu export`.

## 4. Courbe tarifaire unique backend/dashboard

1. En Dynamique, vérifier que `Courbe tarifaire FoxCat` annonce `Luminus Dynamic · all_in` comme source achat.
2. Comparer `Position sur la courbe dynamique` avec le graphique du dashboard.
3. Vérifier que le point courant se trouve dans la même zone BAS / MEDIAN / HAUT.
4. Vérifier que les heures futures proviennent de `today/tomorrow` Luminus Dynamic.
5. Basculer en HP/HC et vérifier que la même carte devient une courbe HP/HC construite avec ComfyFlex et les plages configurées.
6. Vérifier que le graphique et la décision économique utilisent le même nombre de points et les mêmes prix.

## 5. Autoconsommation partielle

Créer un cas Boiler 1800 W avec surplus PV inférieur à 1800 W mais non nul.

- vérifier que FoxCat calcule le complément réseau ;
- vérifier le coût effectif courant ;
- en MEDIAN, vérifier qu'une chauffe peut être autorisée si le coût effectif est meilleur/équivalent au meilleur achat futur ;
- vérifier qu'un prix haut bloque toujours un nouveau prélèvement opportuniste hors sécurité/confort ou couverture solaire complète économiquement pertinente.

## 6. Anti-régression

- cycle machine actif : jamais interrompu ;
- sécurité Boiler 68 °C : prioritaire ;
- Compensation : PRI 100 % ;
- Energy Bus : ACK/NOK inchangé ;
- Métronome : cadence réseau inchangée.
