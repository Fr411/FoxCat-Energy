# FoxCat Energy 1.6.158 — Audit d'impact

## Périmètre

Source : **1.6.157 Dynamic Arbitrage**  
Cible : **1.6.158 — Tarification cohérente, courbe Luminus & Accounting signé**

Cette version corrige le socle tarifaire et financier. Elle ne modifie pas MachineCycleManager, Energy Bus, Machine Learning ni les modes Eco / ECS solaire / Manuel / Zéro injection.

## Règles tarifaires officielles

- **Dynamique** : Luminus Dynamic est la référence financière exclusive.
  - achat courant : `sensor.luminus_luminus_dynamic_wallonia_prix_actuel`
  - heure suivante : `sensor.luminus_luminus_dynamic_wallonia_prix_heure_suivante`
  - réinjection : `sensor.luminus_luminus_dynamic_wallonia_prix_d_injection`
  - courbe : attributs `today` / `tomorrow`, champ `all_in`
  - courbe export : attributs `today` / `tomorrow`, champ `injection`
- **HP/HC** : Luminus ComfyFlex est la référence financière exclusive.
  - HP : `sensor.luminus_luminus_comfyflex_wallonia_prix_heures_pleines_jour`
  - HC : `sensor.luminus_luminus_comfyflex_wallonia_prix_heures_creuses_nuit`
  - réinjection : `sensor.luminus_luminus_comfyflex_wallonia_prix_d_injection`

Le dashboard officiel consomme les entités natives FoxCat `prix_achat_actif` / `prix_achat_suivant` et la nouvelle entité `Courbe tarifaire FoxCat`. Cette dernière expose exactement la série normalisée utilisée par le backend : Luminus Dynamic en Dynamique, ComfyFlex + plages configurées en HP/HC. Le graphique et le moteur ne peuvent donc plus diverger.

Le dashboard client historique fourni avec la release (`homefoxcat_dashboard_client_1.6.158.yaml`) a également été harmonisé : aucune référence directe à ComfyFlex ne subsiste pour afficher un prix « actif » générique.

## Courbe dynamique

Le parseur de prix comprend explicitement `all_in` et `injection`. La position courante est calculée sur la courbe Luminus Dynamic connue :

`position = (prix_courant - minimum_courbe) / (maximum_courbe - minimum_courbe)`

Nouveaux capteurs :

- Position sur la courbe dynamique (%)
- Zone de la courbe dynamique (BAS / MEDIAN / HAUT)
- Avantage économique autoconsommation (€/kWh)
- Courbe tarifaire FoxCat (attributs achat/réinjection, source, position courante)

## Réinjection

Convention normalisée FoxCat :

- valeur `> 0` = revenu de réinjection ;
- valeur `= 0` = neutre ;
- valeur `< 0` = coût pour réinjecter.

Pour Luminus Dynamic, cette convention est forcée à `positif = revenu`, même si une ancienne configuration 1.6.157 avait persisté l'ancienne convention.

Règle PRI souveraine : **si l'export est rémunérateur, le PRI est 100 %**, même si le prédictif tarifaire est désactivé.

## Accounting

Le bilan financier devient explicitement signé :

`coût_net = coût_achat + coût_réinjection - revenu_réinjection`

Nouveaux compteurs :

- `export_revenue_eur`
- `export_cost_eur`
- `net_export_value_eur`

Le champ historique `export_value_eur` est conservé comme alias du revenu brut de réinjection pour compatibilité.

Les prix d'achat négatifs sont désormais comptabilisés comme valeurs négatives et ne sont plus écrasés à zéro.

## Arbitrage dynamique

Le moteur continue d'utiliser la position BAS / MEDIAN / HAUT, mais la décision ne se limite plus à cette bande. Il calcule également :

- avantage autoconsommation = prix achat - valeur export ;
- part solaire disponible pour une charge ;
- complément réseau nécessaire ;
- coût d'opportunité du solaire réinjectable ;
- coût effectif du Boiler maintenant comparé au meilleur achat futur.

En zone MEDIAN, une charge peut donc être pertinente avec **solaire partiel + complément réseau** si son coût effectif est compétitif. La couverture solaire à 100 % n'est plus une condition absolue.

## Terminologie

Le libellé utilisateur officiel est **Injection tarifée**. Une migration interne silencieuse conserve la compatibilité avec les anciennes configurations.

## Anti-régression fonctions

Inventaire AST :

- 1.6.157 : **348 fonctions/méthodes**
- 1.6.158 : **352 fonctions/méthodes**
- ajoutées : **4** (`EnergyAccounting._add_signed` + les 3 méthodes de `FoxCatTariffCurveSensor`)
- supprimée : **0**

Fichiers critiques identiques bit pour bit :

- `machine_cycle.py`
- `energy_bus.py`
- `machines.py`
- `machine_learning.py`
- `engine/load_guard.py`
- `engine/modes/eco.py`
- `engine/modes/ecs_solar.py`
- `engine/modes/manual.py`
- `engine/modes/zero_injection.py`
