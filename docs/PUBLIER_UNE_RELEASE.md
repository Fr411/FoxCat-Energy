# Publier une release

Une release se crée depuis GitHub, sans rien installer :

1. Ouvrez **Actions → Publier une release → Run workflow**.
2. Laissez **version** vide : la version suivante de la série `V1.7.N` est calculée (dernière + 1). Saisissez un numéro (ex. `V1.7.666`) pour en imposer un.
3. **target** : `main` par défaut (ou un commit précis). Cochez **prerelease** pour une pré-version.
4. Lancez. Le workflow vérifie le manifeste, refuse un tag déjà existant, crée le tag et la release, avec les notes suivantes :
   - la section « Non publié » du [`CHANGELOG.md`](../CHANGELOG.md) ;
   - les pull requests fusionnées depuis la release précédente (notes automatiques de GitHub).

Avant de publier : `main` doit contenir le code à livrer et la documentation à jour (`readme.md`, `MANUEL.md`, `JOURNAL_VERSIONS.md`).

Retour arrière : supprimez la release et son tag dans GitHub (Releases → Delete, puis Tags). Aucun fichier du dépôt n'est modifié par le workflow.
