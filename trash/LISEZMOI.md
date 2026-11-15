# trash — fichiers mis de côté

Rien ici n'est utilisé par l'intégration ni par les tests. Les fichiers sont déplacés avec `git mv`, donc leur historique est conservé et on peut les remettre à leur place à tout moment. Une fois la V1.7.6 validée, ce dossier peut être supprimé.

| Fichier | Pourquoi |
|---|---|
| `INSTALLATION.txt` | Notice de mise à jour 1.1.0 → 1.2.0, obsolète |
| `PREMIUM_UI_INSTALL.md` | Installation de l'interface Premium 1.6.154, obsolète |
| `README-INSTALL.md` | Contenu repris dans `readme.md` (section Dashboards) |
| `JOURNAL_VERSIONS.md` | S'arrête à 1.7.4, doublon de `CHANGELOG.md` |
| `README_FoxCat_Energy.md` | Présentation longue datant de la V1.3 |
| `patch_coordinator.py` | Script de patch ponctuel, jamais importé |
| `flexible_load_planner.py`, `machine_learning.py`, `tariff_model.py` | Copies à la racine, jamais importées ; les versions utilisées sont dans `custom_components/foxcat_energy/domain/` |
| `dashboard.yaml.yaml` | Ancien dashboard orphelin (430 Ko) à la racine, référencé nulle part |
| `custom_components/foxcat_energy/coordinator.py`, `vpp.py` | Anciennes copies mortes : le moteur actif est `runtime/coordinator.py` et `trading/vpp.py` (le CHANGELOG annonçait déjà leur suppression) |

Les fichiers `__pycache__` qui étaient suivis par git ont été retirés de l'index (ils sont déjà dans `.gitignore`).
