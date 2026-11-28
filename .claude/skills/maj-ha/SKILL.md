---
name: maj-ha
description: Met à jour l'intégration FoxCat Energy dans Home Assistant (via les outils MCP Home Assistant) vers la dernière release GitHub, puis propose le redémarrage. À utiliser quand l'utilisateur demande « mets à jour dans Home Assistant », « installe la dernière version » ou « /maj-ha ».
---

# Mise à jour de FoxCat Energy dans Home Assistant

Procédure à suivre avec les outils MCP Home Assistant (`ha_search`, `ha_call_read_tool`, `ha_call_write_tool`, `ha_manage_backup`). Lis d'abord le guide des bonnes pratiques (`ha_get_skill_guide`).

## 1. Vérifier ce qui est publié et ce qui est installé

1. Dernière release : `mcp__github__get_latest_release` sur `Fr411/FoxCat-Energy` (le tag, par ex. `V1.7.704`).
2. Version installée : cherche l'entité `update.*` de FoxCat Energy (HACS) avec `ha_search`, et lis `installed_version` / `latest_version`. À défaut, lis la version de l'intégration dans les attributs de l'appareil « FoxCat Energy – Système ».
3. Si les versions sont égales : dis-le et arrête-toi. Si la release GitHub est plus récente que `latest_version` de HACS, demande un rafraîchissement du dépôt HACS (service `homeassistant.update_entity` sur l'entité `update.*`), puis relis.

## 2. Sauvegarde avant d'installer

- Fais une sauvegarde avec `ha_manage_backup` (ou vérifie qu'une sauvegarde récente existe) et donne son nom à l'utilisateur. Une mise à jour d'intégration change du code exécuté dans HA : ne l'installe jamais sans sauvegarde.

## 3. Installer

- Appelle le service `update.install` sur l'entité `update.*` de FoxCat Energy (`ha_call_write_tool`), avec `backup: true` si l'entité le propose.
- **Avertissement HACS / Marketplace** : si l'installation est refusée avec `warning_not_accepted`, c'est une acceptation que **seul l'utilisateur** peut donner dans l'interface HACS (par utilisateur). Ne la contourne pas, n'essaie pas de la simuler : explique-le et demande à l'utilisateur d'accepter l'avertissement, puis relance l'étape.
- Relis l'entité : `installed_version` doit égaler le tag publié. Si ce n'est pas le cas, dis-le tel quel.

## 4. Redémarrage (uniquement sur demande)

- Une intégration mise à jour n'est active qu'après redémarrage de Home Assistant. **Ne redémarre jamais sans que l'utilisateur le demande** (il coupe les automatisations quelques minutes).
- Avant un redémarrage demandé : vérifie la configuration (`homeassistant.check_config`), puis redémarre, puis attends que l'appareil « Santé et alertes » repasse sain.

## 5. Après la mise à jour

- Lis les nouveautés dans `CHANGELOG.md` (section de la version installée) et signale ce qui demande une action : nouvelles entités à ajouter aux dashboards, nouvelle version de dashboard à choisir dans le sélecteur « Version du dashboard » (une version personnalisée n'est jamais écrasée), réglages à contrôler.
- Dashboards DEV : avant toute modification, sauvegarde-les (`ha_manage_backup`) et modifie-les par patch JSON avec le verrou `config_hash`.

## Rapport final

Indique : version avant → après, sauvegarde faite, ce qui a été vérifié dans HA et ce qui ne l'a pas été, et l'action restante pour l'utilisateur (acceptation de l'avertissement, redémarrage).

Limites : cette procédure n'a pas été exécutée de bout en bout ; l'entité `update.*` exacte et l'état de l'avertissement HACS se découvrent à l'exécution.
