# Migration FoxCat Energy 1.7.3 → 1.7.4

## Utiliser le dashboard personnalisé
1. Après avoir modifié le dashboard YAML FoxCat, utilisez **Enregistrer mon dashboard personnalisé** dans les entités de diagnostic.
2. La sauvegarde utilisateur et la base de comparaison sont conservées sous `/config/foxcat_energy/`.
3. Après une mise à jour du dashboard FoxCat, utilisez **Appliquer mes personnalisations à la dernière version** pour fusionner les changements sauvegardés.
4. En cas de conflit, FoxCat n’applique pas la fusion. Résolvez les changements incompatibles, puis sauvegardez de nouveau le dashboard personnalisé.

Le dashboard courant est sauvegardé en `.bak` avant application. La fusion ne remplace pas les modifications utilisateur en conflit avec celles du nouveau template.
