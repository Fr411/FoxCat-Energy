# FoxCat Energy 1.6.1-101 — Release de test

## Compteurs journaliers Métronome / Energy Bus

- Le compteur visible de battements Métronome est remis à zéro chaque jour à minuit, heure locale Home Assistant.
- Le numéro visible des trames Energy Bus repart à 0 à minuit puis la première nouvelle trame du jour porte le numéro 1.
- Le numéro visible des messages Energy Bus repart à 1 chaque nouvelle journée.
- Les compteurs de publications principal/secours du Métronome repartent également à zéro quotidiennement.
- Le reset est doublé par une vérification Watchdog : si l'événement exact de minuit est manqué, le changement de date est détecté au prochain passage du Watchdog.

## Sécurité ACK / PRI N+1

- Séparation du numéro de trame journalier visible et d'une séquence technique interne monotone.
- La séquence interne n'est pas remise à zéro à minuit et protège la validation PRI N+1.
- Un ordre PRI en attente juste avant minuit peut donc toujours être validé sur la première trame du jour suivant.
- Les messages Energy Bus encore sans ACK au changement de journée sont clôturés en TIMEOUT de fin de journée avant purge du journal quotidien.
- Les ACK physiques RRCR / Onduleur / Réseau ne sont pas réinitialisés par le simple reset des compteurs visibles.

## Diagnostics ajoutés

Métronome :
- journée du compteur ;
- dernier reset journalier ;
- battements de la journée précédente ;
- trames de la journée précédente ;
- messages Energy Bus de la journée précédente.

Energy Bus :
- nombre de messages aujourd'hui ;
- nombre de messages de la journée précédente ;
- dernier reset journalier.

## Protocole inter-corps conservé

- ACK_REÇU ;
- ACK_TRAITÉ ;
- NOK_BUSY ;
- NOK_REJECTED ;
- TIMEOUT.

La machine à états EMS, le PRI prédictif, le Métronome principal/fallback, les cycles machines, le Boiler, la tarification et le registre FoxCat restent inchangés fonctionnellement.

## Statut

Cette version est une **release de test** destinée à valider le protocole structuré et les compteurs journaliers avant intégration dans une version stable ultérieure.
