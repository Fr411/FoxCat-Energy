# Migration V1.7.1 → V1.7.2

1. Sauvegarder l'installation Home Assistant avant la mise à jour.
2. Mettre à jour le composant vers V1.7.2 et redémarrer Home Assistant.
3. Aucun changement du format de stockage ni migration supplémentaire n'est requis.
4. Les valeurs du Config Flow alimentent les réglages lors de la première initialisation; une modification de l'Options Flow est appliquée lorsqu'elle est détectée.
5. Les réglages effectués ensuite via les entités continuent d'être conservés dans le Store jusqu'à une nouvelle modification de l'Options Flow.
6. Les choix Éco/Confort/Manuel restent indépendants de la source de prix, de la structure tarifaire et de la politique réseau.
7. Le dashboard conserve son numéro indépendant et reste en version 1.7.1 tant qu'une autre version n'est pas sélectionnée.

La mise à jour n'a pas été validée avec un runtime Home Assistant ni des équipements physiques; consulter `TEST_REPORT_1.7.2.md`.
