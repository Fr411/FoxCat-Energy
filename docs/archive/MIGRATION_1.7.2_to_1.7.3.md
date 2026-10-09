# Migration FoxCat Energy 1.7.2 → 1.7.3

## Avant la mise à jour
1. Sauvegardez Home Assistant et exportez vos réglages si nécessaire avec le service `foxcat_energy.save_settings_profile`.
2. Ne supprimez pas les entités existantes : leurs `unique_id` sont conservés.

## Après la mise à jour
- Les anciens modes, politiques réseau et tarifs connus sont normalisés à l’initialisation. Les valeurs non reconnues reçoivent une valeur sûre valide.
- Quatre interrupteurs d’appareils apparaissent dans « Appareils » : onduleur, compteur, boiler et gestion des machines. Désactiver le compteur arrête la régulation; désactiver le boiler demande l’arrêt de chauffe et libère l’onduleur à 100 %.
- Les heures configurables sont désormais exposées par les entités natives `time`. Les valeurs restent sauvegardées dans les réglages de l’intégration.
- La vue « Technique » contient les réglages natifs. Les profils JSON sont stockés sous `/config/foxcat_energy/profiles/`; les noms de profil n’acceptent que lettres, chiffres, `_` et `-`.
- Le sélecteur de dashboard découvre les versions réellement présentes dans `dashboard/versions/`. Un dashboard utilisateur détecté comme personnalisé ne peut pas être remplacé par ce mécanisme.

La version 1.7.3 est une préparation de release : le mainteneur crée le tag et la release après revue.
