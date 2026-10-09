# Migration 1.6.160 → 1.7.0

La migration est automatique au premier chargement.

| Ancien mode 1.6.x | Comportement 1.7.0 | Contexte migré |
|---|---|---|
| Dynamique / Prix dynamique | Éco | Contrat Dynamique + Injection tarifée |
| Bihoraire / ECS solaire / HP/HC | Éco | Contrat Bi-horaire HP/HC |
| Zéro injection / Réinjection refusée | Éco | Politique Zéro injection |
| Économie énergie | Éco | configuration réseau existante conservée |
| Manuel | Manuel | configuration réseau existante conservée |

Après migration, le comportement Éco / Confort / Manuel est indépendant du contrat, du profil de distribution et de la politique réseau.

Aucun compteur Accounting historique n'est reclassé rétroactivement.
