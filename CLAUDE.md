# Règles pour Claude Code — FoxCat Energy

## Documentation : toujours refaire le README et le manuel avant une fusion

Quand un échange se termine par une **fusion** (merge de la branche, de la pull request, ou demande de fusion de l'utilisateur), **refais d'abord** :

1. **`readme.md`** : fonctionnement complet de FoxCat (architecture, tarification, équipements, protections, entités, dashboards, sécurité).
2. **`MANUEL.md`** : configuration pas à pas (installation, assistant, menus, activation progressive, dépannage, retour arrière).

Comment procéder :

- Relis le code et les changements de l'échange (`CHANGELOG.md`, `translations/fr.json`, `config_flow.py`, `const.py`) pour que les deux documents reflètent l'état réel, pas l'état précédent.
- Mets à jour la version affichée (`custom_components/foxcat_energy/manifest.json`) et les liens vers les fichiers de `docs/`.
- Commite les deux fichiers sur la branche **avant** la fusion, dans le même lot de changements.
- Si une partie n'a pas pu être vérifiée dans le code, dis-le dans la réponse au lieu de l'affirmer dans la documentation.

## Fichiers obsolètes

Ne supprime pas les fichiers inutiles : déplace-les avec `git mv` dans `trash/` et ajoute une ligne dans `trash/LISEZMOI.md` (nom du fichier et raison).
