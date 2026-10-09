# FoxCat Energy 1.6.154 — Premium UI

Cette version est une évolution **interface uniquement** de FoxCat Energy 1.6.153.

## Nouveau tableau de bord Premium

La vue d'accueil a été reconstruite pour se rapprocher d'une interface applicative professionnelle plutôt que d'une succession de cartes Home Assistant classiques.

Elle comprend :

- barre de navigation FoxCat intégrée ;
- grand bandeau Hero avec visuel photovoltaïque ;
- état global, mode EMS et tarif actif ;
- flux énergétique animé PV → maison ↔ réseau ;
- bilan énergétique natif FoxCat du jour ;
- performance solaire, autoconsommation et autonomie ;
- panneau Onduleur / PRI ;
- panneau Boiler / ECS ;
- panneau Machines ;
- coûts et tarifs ;
- décision économique EMS ;
- diagnostic Energy Bus / EMS Core / Onduleur Core / Métronome.

Toutes les valeurs dynamiques utilisent le **registre FoxCat** (`[[foxcat:...]]`).

## Images locales

Les images Premium sont embarquées dans :

`custom_components/foxcat_energy/dashboard/assets/`

FoxCat les synchronise automatiquement vers :

`/config/www/foxcat_energy/premium/`

Elles sont ensuite accessibles au dashboard via :

`/local/foxcat_energy/premium/...`

## Interactions

Les panneaux principaux ouvrent les vues détaillées déjà existantes :

- Énergie → `energie`
- Onduleur → `pri`
- Boiler → `boiler`
- Machines → `appareils`
- Économie → `couts`
- Diagnostic → `technique`
- Réglages → `conf`

La décision économique ouvre directement le `more-info` de son capteur.

## Compatibilité et sécurité

Aucun fichier de logique EMS, PRI, Energy Bus, machines, tarification ou apprentissage n'a été modifié.

Seul `dashboard.py` reçoit quatre fonctions de synchronisation des images Premium. Elles ne participent à aucune décision énergétique.

Le comportement existant de régénération est conservé : un dashboard utilisateur existant n'est jamais écrasé au démarrage. La commande **Régénérer le dashboard** reste nécessaire pour appliquer le nouveau template à un dashboard déjà présent.
