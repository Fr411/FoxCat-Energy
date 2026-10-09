# FoxCat Energy 1.6.0 — modèle énergétique unifié et registre FoxCat

## Sources énergétiques

FoxCat Energy repart sur deux mesures physiques obligatoires :

1. **Puissance réseau signée** ;
2. **Production photovoltaïque**.

Convention par défaut du réseau :

- valeur positive = prélèvement ;
- valeur négative = réinjection.

La convention inverse reste sélectionnable dans la configuration.

À partir de ces deux sources, FoxCat calcule lui-même :

- consommation maison ;
- prélèvement réseau positif ;
- réinjection réseau positive ;
- puissance réseau signée normalisée ;
- bilans et grandeurs dérivées déjà exposés par l'intégration.

Les installations 1.5.x conservent le chemin legacy tant que la nouvelle source réseau signée n'a pas été configurée.

## Métronome et fallback

Le capteur réseau signé principal est aussi la référence de synchronisation du métronome. Le fallback est désormais défini comme **une seconde puissance réseau signée**. En cas de bascule, FoxCat utilise le même capteur de secours à la fois pour le battement et pour la valeur réseau : le snapshot ne mélange donc pas l'horloge du secours avec une mesure principale périmée.

## Ordre fonctionnel officiel

L'ordre suivant devient canonique et partagé par les menus, le registre et les diagnostics :

1. Sources énergétiques
2. Énergie
3. Onduleur
4. EMS
5. Energy Bus
6. Machines
7. Boiler
8. Tarification
9. Métronome
10. Diagnostic

Le libellé utilisateur **PRI / Onduleur** est remplacé par **Onduleur**. PRI reste le nom du moteur interne.

## Registre FoxCat

Ajout d'un registre central `registry.py`.

- Les entités FoxCat natives sont résolues via leur `unique_id` dans le registre Home Assistant.
- Les sources physiques sont résolues depuis la configuration FoxCat.
- Les anciennes entités utilisées par le dashboard restent centralisées comme bindings legacy.
- Le modèle dashboard embarqué ne contient plus aucun `entity_id` brut : toutes les références passent par `[[foxcat:<rôle>]]` puis sont résolues lors de la génération.
- Ajout du capteur diagnostic **Registre des entités FoxCat** avec ordre, bindings résolus, indisponibles et classement par section.

Cette architecture évite qu'un suffixe Home Assistant (`_2`, etc.) ou qu'un renommage d'une entité FoxCat native casse le dashboard régénéré.

## Dashboard

- Conservation des cartes existantes : aucune suppression volontaire du dashboard historique.
- Ajout d'une nouvelle carte **Boiler** dans la section Boiler ECS.
- La nouvelle carte utilise exclusivement le registre FoxCat.
- Le bouton **Régénérer le dashboard FoxCat** résout les entités au moment de l'écriture et crée toujours une sauvegarde `dashboard.yaml.bak` avant remplacement.
- Le démarrage de Home Assistant ne remplace jamais un dashboard utilisateur déjà présent.

## Energy Bus

Ajout de capteurs dédiés :

- état Energy Bus ;
- numéro de trame ;
- dernière trame ;
- source de la dernière intention ;
- action de la dernière intention ;
- delta de puissance de la dernière intention.

## Compatibilité

Les moteurs EMS, PRI prédictif 1.5.5, ACK RRCR, protections machines, boiler, tarification et comptabilité existants sont conservés.
