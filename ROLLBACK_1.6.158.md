# FoxCat Energy 1.6.158 — Rollback

En cas de comportement inattendu :

1. conserver une copie du Store FoxCat et des diagnostics ;
2. réinstaller l'archive 1.6.157 ;
3. redémarrer Home Assistant ;
4. vérifier le régime tarifaire et les sources de prix ;
5. ne pas modifier les sécurités Boiler ni les cycles machines protégés pendant le diagnostic.

Le changement de libellé `Injection tarifée` est migré depuis `Injection facturée`; un retour 1.6.157 peut donc nécessiter de resélectionner la politique réseau correspondante dans l'interface.
