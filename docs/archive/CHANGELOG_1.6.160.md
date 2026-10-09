# FoxCat Energy 1.6.160 — Dynamic Coherence & Boiler Solar-First

## Synchronisation Mode / Tarification

- `Mode EMS = Dynamique` impose `Régime tarifaire = Dynamique`.
- `Mode EMS = Dynamique` impose `Politique réseau = Injection tarifée`.
- Une tentative de modifier ces deux paramètres pendant le mode Dynamique est ramenée à la valeur cohérente.
- Au démarrage, une configuration persistée incohérente est normalisée automatiquement.

## Bihoraire

- Le mode affiché `ECS solaire` devient `Bihoraire`.
- L'ancien moteur `engine/modes/ecs_solar.py` reste inchangé bit pour bit.
- Les anciennes valeurs `ECS solaire`, `Maxi solaire`, `Bi-horaire` et `HP/HC` migrent vers `Bihoraire`.
- `Bihoraire` synchronise `Bi-horaire HP/HC` + `Injection tarifée`.

## Boiler Dynamic V2

Nouvelle branche `engine/modes/dynamic_boiler_v2.py`, utilisée uniquement lorsque :

`Mode = Dynamique` **et** `Régime = Dynamique`.

Règles :

1. sécurité 68 °C souveraine ;
2. surplus solaire suffisant pour couvrir la résistance -> BOOST jusqu'à 65 °C, quelle que soit la position Day-Ahead ;
3. sans surplus solaire suffisant, aucun BOOST réseau 65 °C ;
4. position <= 30 % -> chauffe confort 45 °C autorisée ;
5. position 30–65 % -> fallback Dynamic jusqu'à 45 °C si température sous le seuil de reprise, ou réservation Day-Ahead ;
6. position > 65 % -> aucune nouvelle chauffe réseau Boiler.

L'ancienne méthode `_apply_dynamic_boiler_arbitrage()` reste présente pour audit/rollback mais n'est plus appelée par la boucle de décision.

## Dashboard

- Vue Boiler remplacée par une vue unique : températures, puissance, énergie manquante, durée estimée, exécution, décision Dynamic, seuils 30/65 %, cohérence Mode/Tarif/Réseau et graphique 24 h.
- Vue Day-Ahead : Mode, Régime et Politique réseau visibles avec les deux seuils.
- Les libellés `Prix dynamique` et `ECS solaire` sont remplacés visuellement par `Dynamique` et `Bihoraire`.

## Anti-régression

- fonctions/méthodes : 377 -> 378 ;
- ajoutées : 1 ;
- supprimées : 0 ;
- MachineCycleManager, Energy Bus, Machine Learning, Eco, moteur historique Bihoraire/HP-HC, Manuel, Zéro injection et load_guard : identiques bit pour bit à 1.6.159.
