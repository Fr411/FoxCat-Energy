# FoxCat Energy 1.6.153 — Comparateur économique HP/HC & dynamique

## Objectif

Faire évoluer FoxCat vers un EMS technico-économique sans polluer Energy Bus avec des recommandations de prix et sans modifier l'algorithme prédictif de la politique **Injection facturée**.

## Ajouté

- Nouveau moteur Python local `economic_optimizer.py`.
- Comparateur économique HP/HC déterministe à partir des tarifs ComfyFlex HP/HC et des plages configurées.
- Comparateur dynamique capable d'exploiter :
  - prix d'achat actuel ;
  - prix d'achat suivant ;
  - série optionnelle de prix futurs d'achat ;
  - prix de réinjection actuel ;
  - série optionnelle de prix futurs de réinjection ;
  - minimum/moyenne/maximum disponibles comme contexte existant.
- Parseur générique de séries de prix Home Assistant, sans dépendance cloud ou SDK fournisseur.
- Comparaison du coût réel d'un démarrage machine en intégrant le **coût d'opportunité du solaire** : un kWh PV autoconsommé vaut la recette d'export abandonnée, et non 0 €.
- Utilisation des profils machines déjà collectés : durée moyenne et énergie moyenne des 10 derniers cycles lorsque disponibles.
- Calcul du meilleur créneau futur et de l'économie potentielle estimée.
- Nouveau switch `Optimisation économique des charges flexibles`.
- Nouveaux réglages : horizon du comparateur, économie minimale avant report, marge économique export et surplus solaire minimum.
- Convention explicite du signe de réinjection dynamique :
  - défaut Luminus : prix brut négatif = rémunération ;
  - option générique : prix positif = rémunération.
- Capteur **Décision économique EMS** avec attributs détaillés.
- Capteurs : meilleur prix futur, meilleur créneau économique et économie potentielle.
- Un capteur de choix économique est également créé pour chaque machine configurée.
- Dashboard Tarification : affichage de la décision économique et du meilleur créneau.

## Comportement HP/HC

- Les plages HP/HC sont connues à l'avance et peuvent être comparées sur l'horizon configuré.
- En HP, un nouveau cycle flexible peut être reporté vers HC si l'économie dépasse la marge configurée.
- Un surplus PV peut rendre un démarrage immédiat plus intéressant que l'attente HC.
- Si la valeur de réinjection est supérieure au coût futur d'achat, FoxCat peut recommander d'exporter maintenant et de reporter la charge.
- Les cycles déjà démarrés/protégés ne sont jamais interrompus par l'optimisation économique.

## Comportement dynamique

- FoxCat compare le coût actuel au meilleur prix futur disponible.
- Si l'export est coûteux (valeur économique négative), l'autoconsommation du surplus est favorisée.
- Si la rémunération d'export est supérieure au meilleur coût futur d'achat avec la marge configurée, FoxCat peut préférer exporter maintenant puis consommer plus tard.
- Un prix d'achat négatif favorise immédiatement la consommation flexible.
- En l'absence d'une vraie série future, le comparateur retombe sur les informations actuel/H+1 disponibles et baisse son niveau de confiance.

## Energy Bus

- **Aucune recommandation économique n'est publiée sur Energy Bus.**
- Les séries de prix futurs rafraîchissent seulement les entités du comparateur.
- Energy Bus reste réservé aux échanges opérationnels entre les cœurs et modules actifs.

## Onduleur

- Politique **Compensation** : cible désormais directement **100 %** à chaque décision.
- Politique **Injection facturée** : algorithme prédictif inchangé.

## Machines

- Le comparateur économique intervient uniquement sur l'autorisation d'un **nouveau démarrage automatique**.
- Un cycle actif/protégé reste souverain.
- Les plages horaires utilisateur et protections existantes restent appliquées.

## Anti-régression

- V1.6.152 : 309 fonctions/méthodes.
- V1.6.153 : 331 fonctions/méthodes.
- Fonctions supprimées : 0.
- Fonctions ajoutées : 22.
