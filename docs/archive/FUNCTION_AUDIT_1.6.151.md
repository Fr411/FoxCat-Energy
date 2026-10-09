# Audit anti-régression — FoxCat Energy 1.6.150 → 1.6.151

## Résumé

- Fonctions / méthodes 1.6.150 : **286**
- Fonctions / méthodes 1.6.151 : **293**
- Fonctions supprimées : **0**
- Fonctions ajoutées : **7**

## Fonctions ajoutées

- `FoxCatEnergyCoordinator._async_user_switch_call`
- `FoxCatEnergyCoordinator._classify_pri_grid`
- `FoxCatEnergyCoordinator.async_user_boiler_override`
- `FoxCatEnergyCoordinator.async_user_start_machine`
- `FoxCatEnergyCoordinator.async_user_stop_machine`
- `MachineCycleManager.force_start`
- `MachineCycleManager.force_finish`

## Fonctions supprimées

Aucune.

## Vérifications ciblées

- Le chemin PRI qui appelait `_classify_pri_grid` dispose maintenant de l'implémentation attendue.
- La machine à états EMS historique est conservée.
- Energy Bus, métronomes, workers Onduleur et Boiler sont conservés.
- Les commandes utilisateur machines utilisent le gestionnaire de cycles historique au lieu de le contourner.
- Les protections thermiques Boiler restent souveraines.

## Conclusion

La 1.6.151 est une correction additive de la 1.6.150. Aucune fonction Python historique de la 1.6.150 n'a été supprimée.
