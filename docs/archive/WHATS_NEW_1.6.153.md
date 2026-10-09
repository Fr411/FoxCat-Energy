# What's New — FoxCat Energy v1.6.153

## EMS économique

FoxCat ajoute un comparateur économique local pour les régimes **HP/HC** et **Dynamique**.

- Comparaison du prix d'achat actuel avec les créneaux futurs.
- Prise en compte de la valeur de réinjection.
- Prise en compte du coût d'opportunité du solaire autoconsommé.
- Utilisation de la durée et de l'énergie moyennes apprises pour chaque machine.
- Choix entre démarrer maintenant, reporter, absorber un surplus ou favoriser l'export.

## HP/HC

FoxCat connaît les plages HP/HC configurées et construit lui-même la courbe tarifaire future. Les tarifs ComfyFlex HP et HC sont utilisés pour comparer le coût estimé d'un cycle maintenant avec un démarrage futur.

## Dynamique

FoxCat peut exploiter les prix actuel/H+1 et, si disponibles, des séries de prix futurs d'achat et de réinjection fournies par Home Assistant.

La convention du signe de réinjection est configurable. Le défaut reste compatible Luminus : prix brut négatif = rémunération.

## Décision économique EMS

Nouveau capteur **Décision économique EMS** avec :

- décision et raison ;
- régime tarifaire ;
- niveau de confiance ;
- meilleur prix futur ;
- meilleur créneau ;
- économie potentielle ;
- choix économique détaillé par machine.

Le dashboard Tarification affiche également la décision et le meilleur créneau.

## Energy Bus

Les recommandations économiques ne sont **pas publiées sur Energy Bus**. Le bus reste réservé aux communications opérationnelles entre les cœurs.

## Machines

L'optimisation économique agit uniquement sur les **nouveaux démarrages automatiques**. Un cycle déjà actif/protégé n'est jamais interrompu.

## Onduleur

- Compensation : cible directe **100 %**.
- Injection facturée : moteur PRI prédictif inchangé.

## Anti-régression

- 1.6.152 : 309 fonctions/méthodes.
- 1.6.153 : 331 fonctions/méthodes.
- Suppressions : 0.
