# Installation — FoxCat Premium UI 1.6.154

## Prérequis

La vue Premium utilise `custom:button-card`, déjà utilisé par le dashboard FoxCat 1.6.153.

Aucune nouvelle carte frontend n'est obligatoire.

## Installation depuis GitHub

1. Remplacer/mettre à jour le dossier `custom_components/foxcat_energy` avec cette version.
2. Redémarrer Home Assistant.
3. FoxCat copie automatiquement les images Premium dans `/config/www/foxcat_energy/premium/`.
4. Dans FoxCat, lancer **Régénérer le dashboard**.
5. FoxCat crée auparavant `dashboard.yaml.bak` si le dashboard existait déjà.
6. Ouvrir la vue `Accueil` (`Emsdash`).

## Si une image ne s'affiche pas immédiatement

Vider le cache de l'application Home Assistant ou recharger la page. Les images sont servies via `/local/foxcat_energy/premium/`.

## Retour arrière

- restaurer `foxcat_energy/dashboard.yaml.bak`, ou
- remettre le template dashboard 1.6.153.

Aucune donnée EMS n'est migrée ou modifiée par la Premium UI.

## Développement

Une copie de référence du rendu visuel se trouve dans :

`docs/PREVIEW_FOXCAT_PREMIUM_UI.png`

Les ressources sources se trouvent dans :

`custom_components/foxcat_energy/dashboard/assets/`
