# FoxCat Energy 1.7.3 — préparation

## Nouveautés
- Menus de sélection segmentés pour le mode EMS, la politique réseau et le régime tarifaire; options, valeurs actives, descriptions et icônes sont alignées.
- Templates YAML d’onduleur, compteur, boiler et machines chargés et validés avec le catalogue matériel.
- Switches par appareil avec arrêt chaudière, libération PRI à 100 % et arrêt de la régulation si le compteur est désactivé. Les cycles machines protégés restent prioritaires.
- Vue Technique alimentée par les entités natives `number`, `switch` et `time`, avec réglages regroupés et boutons de profils.
- Services `save_settings_profile`, `load_settings_profile` et `reset_settings`; les bornes numériques et valeurs sont vérifiées avant application.
- Sélecteur de versions dashboard alimenté par les fichiers disponibles; sauvegarde `.bak`, restauration précédente et rollback sur erreur.
- Version moteur et version du dashboard actif affichées dans le tableau de bord.

## Compatibilité et publication
- Les `unique_id` déjà publiés sont conservés; les nouveaux appareils et le select de version ont des identifiants distincts.
- Le dashboard existant est conservé au démarrage et une personnalisation détectée n’est jamais remplacée.
- Cette branche prépare la version 1.7.3. Le tag `v1.7.3` et la release GitHub sont réservés au mainteneur après revue.
