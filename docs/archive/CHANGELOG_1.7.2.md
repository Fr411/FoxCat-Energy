# FoxCat Energy 1.7.2

Version corrective basée sur le code V1.7.1 présent dans cette branche.

## Changements

- Reprise des réglages initiaux du Config Flow et des choix explicites de l'Options Flow.
- Suppression du verrouillage qui faisait dépendre la tarification et la politique réseau du comportement EMS.
- Implémentation du chemin d'extraction des séries Day-Ahead depuis les attributs Home Assistant, avec prise en charge des courbes fournisseur privilégiées.
- Pas d'utilisation de prévisions dynamiques pour les tarifs non dynamiques; HP/HC et Simple conservent une série déterministe.
- Dispatch Confort vers la stratégie de base Éco; arbitrage boiler Day-Ahead pour les comportements autres que Manuel.
- Calcul des pics, fenêtres favorables, meilleurs créneaux restants et données J/J+1 dans le Price Analyzer.
- Ajout de tests unitaires ciblés et mise à jour du rapport de validation.

## Compatibilité et limites

- Aucun changement de format de stockage n'est introduit; le marqueur de migration du modèle de configuration reste `1.7.1`.
- Le dashboard est indépendant et reste sélectionné/recommandé en version 1.7.1.
- La validation Home Assistant, frontend et équipements physiques n'a pas été effectuée dans cet environnement.
- Cette version corrige des défauts ciblés mais ne prétend pas satisfaire l'ensemble des critères d'acceptation du chantier complet V1.7.1.
