# FoxCat Energy 1.5.6 — PRI souverain par trame et commande boiler utilisateur

## PRI souverain

- Chaque publication d'un capteur utile au PRI déclenche un recalcul, y compris une republication à valeur identique via `state_reported` / `last_reported` lorsque Home Assistant l'expose.
- Sources suivies : PV, consommation maison, import réseau, export réseau, réseau signé historique, métronome principal et métronome de secours.
- Suppression du throttle 30 s pour le PRI. Le métronome 30 s reste l'horloge du CORE et le fallback si aucun callback physique exploitable n'est reçu.
- Aucun mode EMS, délai boiler, hystérésis de score, ACK N+1, état de délestage ou hypothèse « PV au plafond » ne bloque plus un recalcul PRI valide.
- Le retour RRCR inconnu n'annule plus une trame : FoxCat repart du dernier niveau logique et réécrit le palier calculé.
- La commande RRCR n'attend plus un ACK avant de rendre la main. La trame suivante valide N+1 puis recalcule dans tous les cas.
- Verrou physique RRCR séparé du verrou des actions CORE/boiler.
- Le délestage ne force plus le PRI à 100 % et ne l'annule plus.
- Les modes EMS ne désarment plus le PRI.
- En « Injection facturée », la consommation maison normalisée devient la grandeur feed-forward principale. Une hausse de charge peut donc faire remonter immédiatement le palier sans attendre la propagation complète sur le compteur réseau.
- En « Compensation », le palier idéal est recalculé directement à 100 % à chaque trame.

## Mesures FoxCat normalisées

FoxCat crée et expose ses propres mesures cohérentes pour l'EMS :

- puissance de production photovoltaïque ;
- consommation réelle maison ;
- puissance réinjectée au réseau ;
- puissance prélevée au réseau ;
- balance réseau ;
- consommation maison calculée par `PV + import - export` ;
- écart entre capteur maison direct et bilan FoxCat ;
- qualité et sources des mesures ;
- compteur et source des publications ayant déclenché le PRI.

Si le capteur maison direct est indisponible, le bilan FoxCat peut prendre le relais. Si un capteur import/export séparé est indisponible, le capteur réseau signé historique peut servir de fallback.

## Boiler — demande utilisateur persistante

- Nouveau switch `Boiler • Marche utilisateur maintenue`.
- Nouveaux boutons `Démarrer le boiler` et `Arrêter le boiler`.
- Une marche demandée explicitement par l'utilisateur traverse les cycles machines protégés, les contraintes HP/HC, l'achat réseau et les stratégies énergétiques normales.
- Un arrêt automatique ordinaire est ignoré tant que la demande utilisateur est mémorisée.
- Deux interruptions restent prioritaires : sécurité thermique et délestage explicite.
- Pendant un délestage, la demande reste mémorisée et l'état indique `DÉLESTAGE EN COURS — DEMANDE MÉMORISÉE`.
- À la fin du délestage, le boiler redémarre automatiquement si la demande utilisateur est toujours active.

## Compatibilité

Aucun élément historique n'est supprimé. Les anciens réglages `pri_enabled`, `pri_score_margin` et `pri_boiler_settle_s` sont conservés pour compatibilité, mais ils ne peuvent plus bloquer le cœur PRI souverain.
