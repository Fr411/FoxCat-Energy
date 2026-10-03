# FoxCat Energy 1.6.158 — Tariff & Finance

## Objectif

Aligner le moteur économique, l'Accounting et les dashboards sur une seule vérité tarifaire selon le régime actif.

## Règles officielles

- Dynamique : **Luminus Dynamic** est la référence financière achat/réinjection.
- HP/HC : **Luminus ComfyFlex** est la référence financière HP/HC.
- Nord Pool / ENTSO-E restent des signaux de contexte/timing et ne remplacent jamais le prix client Luminus.
- Libellé utilisateur : **Injection tarifée**.
- Export rémunérateur : **PRI = 100 %**, indépendamment du kill-switch prédictif.

## Changements moteur

- lecture native des champs `all_in` et `injection` des séries `today/tomorrow` Luminus Dynamic ;
- calcul de la position courante sur la courbe Luminus ;
- coût marginal d'autoconsommation intégrant le coût d'opportunité de l'export ;
- possibilité d'utiliser solaire partiel + complément réseau quand cela reste financièrement pertinent ;
- HP/HC isolé du Dynamic et construit depuis les prix ComfyFlex + plages configurées ;
- courbe tarifaire normalisée commune au backend et au dashboard.

## Accounting

`coût net = coût achat + coût export - revenu export`

Nouveaux champs :

- `export_revenue_eur`
- `export_cost_eur`
- `net_export_value_eur`

Les prix d'achat négatifs restent signés.

## Dashboard

- nouvelle entité **Courbe tarifaire FoxCat** ;
- graphique ApexCharts alimenté par la même courbe que le moteur économique ;
- point « Maintenant » sur le prix actif ;
- achat et valeur de réinjection tracés sur le même axe financier ;
- dashboard client historique harmonisé avec les prix actifs natifs FoxCat.

## Anti-régression

- 1.6.157 : 348 fonctions/méthodes
- 1.6.158 : 352 fonctions/méthodes
- +4
- 0 supprimée

MachineCycleManager, Energy Bus, Machine Learning, Eco, ECS solaire, Manuel et Zéro injection restent sanctuarisés.
