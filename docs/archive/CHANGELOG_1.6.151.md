# FoxCat Energy 1.6.151 — Correctif PRI et commandes utilisateur

## Corrigé

- Correction du crash Onduleur Core provoqué par l'appel à `_classify_pri_grid()` absent en 1.6.150.
- L'ACK réseau PRI classe désormais explicitement la trame en `OK`, `NOK_REINJECTION`, `NOK_PRELEVEMENT` ou `NOK_DONNEES`.
- La sécurité thermique Boiler reste prioritaire même lorsque la régulation automatique est désactivée ou qu'un override utilisateur est actif.

## Ajouté

- Bouton **Démarrage utilisateur** créé automatiquement pour chaque machine FoxCat configurée.
- Bouton **Arrêt utilisateur** créé automatiquement pour chaque machine FoxCat configurée.
- Un démarrage machine utilisateur crée un **cycle protégé** d'origine `USER_BUTTON` afin que l'EMS ne coupe pas la machine à la trame suivante.
- Boiler : boutons **Démarrage utilisateur**, **Arrêt utilisateur** et **Retour automatique EMS**.
- Boiler : état `boiler_user_override` avec `AUTO`, `FORCE_ON`, `FORCE_OFF`.
- Nouveau capteur **Boiler • Commande utilisateur**.
- Les commandes utilisateur sont publiées sur Energy Bus et accusées comme prises en charge par EMS Core.
- Les appels utilisateur vers les prises sont bornés à 3 secondes et indépendants de l'état d'exécution Boiler.
- Les boutons utilisateur sont regroupés dans le device **FoxCat Energy – Fonctions utilisateur**.
- Le registre FoxCat expose les commandes utilisateur Boiler et résout dynamiquement les commandes des machines configurées.

## Sécurité

- L'override utilisateur Boiler ne peut jamais dépasser la sécurité de température maximale.
- Une fonction Boiler désactivée refuse un démarrage utilisateur.
- Un arrêt sécurité reste autorisé même si la régulation FoxCat est désactivée.

## Anti-régression

- 1.6.150 : 286 fonctions/méthodes.
- 1.6.151 : 293 fonctions/méthodes.
- Supprimées : 0.
- Ajoutées : 7.
