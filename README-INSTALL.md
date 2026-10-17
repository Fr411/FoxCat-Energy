# FoxCat Energy - Dashboard généré automatiquement

## Fichiers GitHub

Copier dans le dépôt :

```text
custom_components/foxcat_energy/
├── __init__.py
├── button.py
├── dashboard.py
└── dashboard/
    └── dashboard.yaml
```

Le reste du composant FoxCat Energy reste inchangé.

## Fonctionnement

Au chargement de FoxCat Energy :

- si `/config/foxcat_energy/dashboard.yaml` n'existe pas, le composant le crée automatiquement ;
- si `/config/foxcat_energy/dashboardmob1.yaml` n'existe pas, le composant crée aussi le dashboard mobile ;
- les fichiers existants ne sont pas écrasés au démarrage ;
- le bouton `Régénérer le dashboard FoxCat` permet de forcer sa régénération ;
- les sélecteurs `Version du dashboard tablette/PC` et `Version du dashboard mobile` changent leurs fichiers indépendamment, avec une sauvegarde `.bak` avant chaque remplacement.

## Enregistrement Lovelace

Home Assistant doit savoir que ce fichier est un dashboard YAML.
Fusionner une seule fois le contenu de `configuration.yaml.snippet` dans `/config/configuration.yaml`, puis redémarrer Home Assistant.
Le snippet enregistre les deux dashboards dans la barre latérale : `foxcat-energy` pour tablette/PC et `foxcat-energy2` pour mobile.

Ne pas modifier directement `.storage/lovelace_dashboards`.
