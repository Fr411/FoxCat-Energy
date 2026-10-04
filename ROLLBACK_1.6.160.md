# Rollback 1.6.160 -> 1.6.159

La 1.6.160 est additive. Pour revenir au comportement précédent :

1. réinstaller l'archive 1.6.159 ;
2. redémarrer Home Assistant ;
3. les valeurs persistées `Bihoraire` et `Dynamique` sont reconnues par les alias de migration de la 1.6.160, mais une 1.6.159 pure attend encore les anciens libellés ; si nécessaire sélectionner manuellement le mode après rollback ;
4. aucune donnée Accounting V2 n'est supprimée par ce correctif.

L'ancienne méthode `_apply_dynamic_boiler_arbitrage()` a été conservée dans `coordinator.py` pour faciliter l'audit du changement.
