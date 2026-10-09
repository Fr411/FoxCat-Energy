# FoxCat Energy 1.6.152 — Collecte machines, dashboard natif et tarifs contextualisés

## Principe de cette release

La 1.6.152 est volontairement **additive**. Le comportement décisionnel du PRI / Onduleur Core, de l’EMS Core et de la machine à états des cycles machines est gelé. Cette version ajoute de l’observation, du contexte Energy Bus et corrige l’affichage des données sans modifier les algorithmes de régulation existants.

## Ajouté — collecte passive des machines

- Nouveau `MachineLearningRecorder` local, 100 % Python et sans service externe.
- Collecte passive par machine de :
  - puissance,
  - courant,
  - tension,
  - état de la prise,
  - état/origine du cycle,
  - contexte réseau / PV / maison,
  - prix actif et période tarifaire.
- Historique borné à 30 cycles par machine et 720 points maximum par cycle.
- Intégration locale de l’énergie consommée pendant le cycle.
- Conservation des profils terminés dans le Store Home Assistant.
- Un cycle actif n’est pas restauré après un redémarrage afin de ne pas intégrer artificiellement la durée d’arrêt Home Assistant.
- Nouveaux capteurs de synthèse par machine : cycles collectés, collecte active, énergie moyenne sur 10 cycles et durée moyenne sur 10 cycles.
- Les capteurs de courant et de tension deviennent configurables en option pour chaque machine.

## Energy Bus

- Chaque trame transporte désormais un contexte `machines` décrivant les machines actives, leur puissance, courant, tension, état de cycle, protection et origine.
- L’information est uniquement contextuelle : elle ne modifie pas la décision des deux cœurs dans cette release.
- Correction du doublon de paramètre `origin` dans `publish_ems_intent()` qui pouvait générer `got multiple values for keyword argument 'origin'`.

## Dashboard

- Migration des KPI journaliers principaux vers les compteurs natifs FoxCat :
  - consommation maison,
  - production photovoltaïque,
  - autoconsommation,
  - prélèvement réseau,
  - réinjection réseau,
  - taux d’autoconsommation et autonomie.
- La carte **Énergie** affiche maintenant explicitement **Réseau prélevé aujourd’hui** en plus des KPI déjà présents.
- Suppression des références legacy pour les principaux bilans journaliers discutés.
- Les coûts journaliers affichés utilisent maintenant l’accounting natif FoxCat intégré trame par trame.

## Tarification

- Le dashboard utilise désormais un prix d’achat **actif** fourni directement par FoxCat.
- En régime dynamique : prix actuel + prix de l’heure suivante.
- En régime bi-horaire : prix de la période active HP/HC + prix de l’autre période.
- Ajout des libellés de prix actif et suivant pour que le dashboard n’ait plus à déduire le régime tarifaire.
- Les coûts journaliers ne sont plus estimés en multipliant toute la journée par le prix instantané affiché ; ils proviennent de l’intégration native FoxCat par trame.

## Gel fonctionnel

Fichiers de décision vérifiés **inchangés** par rapport à 1.6.151 :

- `inverter_core.py`
- `engine/pri.py`
- tout le répertoire `engine/`
- `machine_cycle.py`
- `accounting/manager.py`

Les ajouts dans `coordinator.py` sont limités à la collecte passive, au contexte Energy Bus et aux valeurs génériques d’affichage tarifaire.

## Anti-régression

- 1.6.151 : **293 fonctions / méthodes**.
- 1.6.152 : **309 fonctions / méthodes**.
- Fonctions supprimées : **0**.
- Fonctions ajoutées : **16**.

Voir `FUNCTION_AUDIT_1.6.152.md`.
