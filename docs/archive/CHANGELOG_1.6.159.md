# FoxCat Energy 1.6.159 — Accounting V2 & Dynamic Day-Ahead Scheduler

## Périmètre

Les nouvelles décisions Day-Ahead sont **strictement réservées au mode EMS Prix dynamique avec régime tarifaire Dynamique**. HP/HC, Compensation, Eco, ECS solaire, Manuel et Zéro injection conservent leur comportement historique.

## Day-Ahead

- seuil de prix favorable réglable, 30 % par défaut, calculé sur la position relative min/max de la courbe Luminus Dynamic ;
- seuil de pic réglable, 70 % par défaut ;
- détection du prochain creux et du prochain pic ;
- horizon jusqu'à 36 h avec `today + tomorrow` ;
- recalcul lorsque les prix de demain deviennent disponibles ;
- décision fondée sur la même courbe Luminus Dynamic que le graphique dashboard.

## Machines LL / SL / LV

- respect impératif des plages horaires définies par l'utilisateur ;
- durée apprise sur les 10 derniers cycles prioritaire sur la durée configurée ;
- le cycle complet doit tenir avant la fin de la plage ;
- priorité à l'autoconsommation ;
- complément réseau autorisable sous le seuil favorable ;
- recherche d'une meilleure fenêtre future lorsque le prix actuel est défavorable ;
- un cycle déjà actif/protégé n'est jamais interrompu.

## Boiler

- boost solaire lorsque le surplus couvre la résistance et que l'autoconsommation est économiquement pertinente ;
- boost Day-Ahead jusqu'à la consigne Boost lorsque la position est sous le seuil utilisateur ;
- confort ECS minimum prioritaire ;
- sécurité résistance 68 °C inchangée.

## Accounting V2

Les compteurs physiques sont séparés de la finance :

- consommation maison totale ;
- production PV totale ;
- import réseau total ;
- réinjection réseau totale.

La réinjection ne diminue jamais l'import en kWh. La compensation n'existe que dans le bilan financier :

`coût net = coût achat + coût réinjection - revenu réinjection`

Ventilation native :

- Dynamic : import, export, coût achat, revenu export, coût export, coût net ;
- HP : import/export ;
- HC : import/export ;
- appareils : énergie Dynamic/HP/HC séparée.

Les prix négatifs d'achat restent signés.

## Dashboard

Nouvelle vue `day-ahead` :

- Marché & tendance ;
- graphique Luminus Dynamic achat/réinjection sur 2 jours ;
- réglage du seuil favorable ;
- prochain creux / prochain pic ;
- fenêtres optimales LL / SL / LV ;
- PV total jour, consommation totale jour, import total jour, réinjection totale jour ;
- ventilation financière Dynamic.
