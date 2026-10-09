# Migration V1.6.160 → V1.7.1

1. Sauvegarder la configuration Home Assistant.
2. Installer le composant V1.7.1.
3. Au premier démarrage, les paramètres persistés sont migrés vers un modèle indépendant.
4. Un ancien `Dynamique` devient `price_source = Dynamique Day-Ahead` et `mode = Éco` — il n'est **jamais** converti en Manuel.
5. Un ancien Bihoraire conserve la structure Bi-horaire.
6. `Zéro injection` devient une politique réseau et ne constitue plus un comportement EMS.
7. Le dashboard original V1.6.160 reste disponible séparément.
8. Le retour arrière du dashboard est prévu ; le retour moteur doit être effectué avec une sauvegarde de la configuration.
