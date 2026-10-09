# FoxCat Energy 1.7.0 — Architecture EMS & UX

## Rupture architecturale maîtrisée

La 1.7.0 sépare désormais quatre couches :

- **Comportement EMS** : Éco / Confort / Manuel ;
- **Contrat énergie** : Fixe / Monohoraire, Bi-horaire HP/HC, Dynamique ;
- **Distribution / comptage Belgique** : profils Wallonie, Flandre et Bruxelles ;
- **Politique réseau** : Injection tarifée / Compensation / Zéro injection.

Les anciens modes 1.6.x sont migrés vers ce nouveau modèle sans réécrire l'historique Accounting.

## Boiler charge flexible universelle

- nouveau moteur `engine/flexible_boiler.py` utilisé dans tous les contrats ;
- BOOST solaire prioritaire dans tous les profils de comptage ;
- stockage boost 65 °C réservé au surplus solaire suffisant ;
- fallback réseau conditionné par l'estimation thermique et la confiance des sondes ;
- sonde bas/doigt de gant pondérée à la baisse pendant/après chauffe ;
- sonde haute/contact utilisée pour tendance et détection de puisage ;
- suppression de la priorité ECS absolue basée uniquement sur une température basse dans l'arbitrage Day-Ahead.

## Dynamic

- seuil favorable 30 % conservé ;
- plafond économique 65 % conservé ;
- Confort peut assouplir le seuil de départ via `comfort_relaxation_pct` ;
- affichage du temps restant dans le creux favorable courant ;
- scheduler actif uniquement avec contrat Dynamique et comportement automatique ;
- plages utilisateur et cycles MachineCycleManager restent souverains.

## Réseau belge

Profils disponibles :

- Wallonie · Monohoraire ;
- Wallonie · Bihoraire 2026 ;
- Wallonie · Impact ;
- Wallonie · Exclusif nuit (piloté GRD) ;
- Flandre · Standard ;
- Flandre · Capacité ;
- Bruxelles · Monohoraire ;
- Bruxelles · Bihoraire.

Le profil Wallonie · Impact expose ECO / MEDIUM / PIC et peut bloquer un nouveau départ flexible en PIC lorsque le comportement Éco est actif.

## Dashboard / UX

- **une seule vue principale** ;
- Énergie, Marché & Réseau, Boiler, Appareils, Onduleur, Technique et Diagnostic passent en sous-vues ;
- identité visuelle FoxCat inspirée du logo : fond sombre, halos orange solaire et cyan énergie ;
- fonds spécifiques par sous-vue ;
- cartes Dynamic masquées hors contrat Dynamique ;
- cartes HP/HC masquées hors contrat Bihoraire ;
- carte Impact visible uniquement avec le profil Impact ;
- page Technique transformée en **EMS Configurator** avec explications et réglages comportement/réseau/Boiler/PRI.

## Nettoyage interface

- suppression des éléments présentés comme « IA » dans les dashboards et la configuration ;
- Forecast.Solar reste une source déterministe ;
- Machine Learning reste la couche passive d'apprentissage des cycles.

## Anti-régression

Les fichiers `energy_bus.py`, `machine_cycle.py`, `machine_learning.py`, `accounting/manager.py` et `engine/load_guard.py` restent bit pour bit identiques à la 1.6.160.
