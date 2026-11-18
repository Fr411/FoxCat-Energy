# Flux Node-RED — LOGO!8 ↔ Home Assistant

| Fichier | Rôle |
|---|---|
| `backup/flows-original-2026-11-18.json` | Export d'origine, intact (retour arrière : importer ce fichier). |
| `flows-reorganise.json` | Flux réorganisé par fonction, avec portes avant chaque écriture dans le LOGO!8. |

## Onglets
1. **Supervision LOGO8** : statut de la liaison S7, pose `global.logo8_en_ligne`.
2. **Éclairages** : boutons HA → NI1…NI12 + retour d'état Q.
3. **Porte de garage** : impulsion NI8.
4. **Chauffage & énergie** : chauffage sol, PRI L1–L4, poêle, chauffe-eau.
5. **Entrées LOGO → HA** : entrées I1–I24 recopiées dans HA (lecture seule), ambiances, toggles.

## Corrections
- **Porte 🔒** (nœud `function`) devant chacun des 19 `s7 out` actifs : n'accepte qu'un booléen, bloque l'écriture si le LOGO est connu hors ligne (état inconnu = on laisse passer).
- Noms des `s7 out` = variable + adresse réelle (ex. `NI 17 ( Poele ) · X6.1`) ; les anciens « 5.5 (Poele) » / « 5.6 (Boiler) » étaient trompeurs.
- `I06 High Freq` (écriture sur une entrée physique) : nœud **désactivé**, conservé.
- Groupes aux noms doublons renommés ; groupes imbriqués aplatis ; onglets « Flux 1 » et « Flux 3 » (vides après déplacement) retirés.

## Non modifié (à vérifier)
- Table de variables de l'endpoint S7 : adresses en double (M17–M24 = M09–M16, M33…64 = M25, NQ1 à X1390.0 et X1.0).
- Entrées I07, I10, I11, I13, I14, I15 lues deux fois (onglets 5 et éclairages).
- Impulsion des boutons : `true` puis `false` immédiat (le garage utilise 1 s de délai).
- Le texte exact du statut du nœud `s7 in` (fill vert/rouge, « online ») n'a pas pu être vérifié sans l'installation.
