# FoxCat Energy 1.6.157 — Rollback immédiat

## Option 0 — Repli fonctionnel sans changer le code

Si le problème concerne uniquement le nouvel arbitrage dynamique :

1. couper `switch.foxcat_predictive_pricing_enabled` ;
2. si nécessaire, couper `switch.foxcat_solar_forecast_arbitrage` ;
3. attendre la prochaine publication réseau.

Le comparateur dynamique repasse sur son comportement standard lorsque le prédictif prix est désactivé. Cette option permet de stabiliser rapidement l'installation avant un rollback logiciel.

## Option 1 — Retour complet à 1.6.156 Professional

1. Sauvegarder les logs utiles et l'état des entités FoxCat.
2. Arrêter Home Assistant.
3. Remplacer entièrement :

`/config/custom_components/foxcat_energy/`

par le dossier de la **1.6.156 Professional**.

4. Vérifier que le `manifest.json` restauré annonce `1.6.156`.
5. Redémarrer Home Assistant.
6. Contrôler : réseau signé, EMS Core, PRI, Boiler, Machines, Tarification.

Aucune migration de stockage irréversible n'est introduite par 1.6.157. Les nouvelles clés d'options Boiler peuvent rester dans la ConfigEntry : la 1.6.156 les ignore. Les nouvelles entités peuvent apparaître temporairement indisponibles dans le registre Home Assistant ; ne pas les supprimer avant d'avoir confirmé la stabilité du rollback.

## Option 2 — Git

Avec une arborescence propre et le patch livré :

```bash
git apply -R FoxCat-Energy-1.6.156-to-1.6.157-Dynamic-Arbitrage.patch
```

Puis redémarrer Home Assistant.

Alternative recommandée si des commits ont déjà été ajoutés : revenir au tag/commit connu de la 1.6.156 plutôt que forcer un reverse patch.

## Vérifications après rollback

- Version affichée : 1.6.156.
- Régime HP/HC : fonctionnement normal.
- Dynamique : comportement 1.6.156.
- PRI : niveaux et ACK habituels.
- Boiler : sécurité Résistance 68 °C toujours disponible selon la baseline 1.6.156 Professional.
- MachineCycleManager : cycles protégés visibles et intacts.
- Accounting : compteurs journaliers continus.

## Données à ne pas supprimer pendant le rollback

Ne supprimer ni les historiques Home Assistant ni les entrées du registre d'entités avant validation. Le rollback porte uniquement sur le code du custom component ; les mesures historiques et la configuration utilisateur doivent être conservées.
