# FoxCat Energy 1.6.1

## Energy Bus — ACK inter-corps

- Ajout d’un ACK de transport explicite entre EMS Core et le corps Onduleur.
- Distinction entre message reçu, message traité, NOK temporaire et timeout.
- Un message EMS -> Onduleur porte désormais un identifiant unique.
- Le corps Onduleur répond ACK_REÇU lorsqu’il prend connaissance du message sur une trame valide.
- Après calcul PRI, le message passe ACK_TRAITÉ.
- Si le corps ne peut pas traiter la demande (snapshot invalide, garde PRI, RRCR incohérent), il répond NOK avec la raison.
- Si aucun ACK n’est reçu dans le délai, Energy Bus marque le message TIMEOUT.
- Les ACK Energy Bus sont distincts des ACK physiques RRCR / Onduleur / Réseau.

## Machine à états EMS

- Conservation vérifiée de la machine à états : ACQUISITION -> DECISION -> WAIT_ACK.
- Ajout d’un diagnostic de santé de la machine à états.
- Ajout d’un compteur de transitions.
- Ajout de la dernière transition et de son horodatage.
- Le Watchdog contrôle maintenant aussi la validité de la phase et réinitialise le CORE si une phase incohérente est détectée.

## Diagnostics

Nouvelles entités Energy Bus :
- numéro du dernier message ;
- ACK inter-corps ;
- raison de l’ACK ;
- corps ayant répondu ;
- dernier échange Energy Bus ;
- nombre de messages en attente.

Nouvelles entités EMS :
- état de la machine à états ;
- compteur de transitions ;
- dernière transition ;
- horodatage de la dernière transition.
