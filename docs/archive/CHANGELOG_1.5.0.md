# FoxCat Energy 1.5.0 — Double cœur EMS

## Conservé
Le EMS CORE existant n'est pas remplacé : boiler, fallback thermiques, machines,
cycles protégés, priorité utilisateur, délestage, modes, comptabilité et logique
de sécurité restent en place.

## Nouveau
- `EnergyBus` : communication immédiate entre EMS CORE et EMS Onduleur.
- `InverterCore` : second cœur spécialisé PV/RRCR.
- EMS Onduleur cadencé par la trame réseau/réinjection, plus par l'horloge 30 s.
- Une trame réseau = une décision EMS Onduleur.
- Comparateur PV/plafond : détecte PV bridé / potentiel supplémentaire /
  maximum solaire instantané.
- Sélecteur indépendant `Politique réseau` :
  - Compensation : onduleur progressivement libéré à 100 %, réseau tampon.
  - Injection facturée : faible injection tolérée, léger import recherché.
- Régime tarifaire distinct : HP/HC ou Dynamique.
- Suppression des entrées manuelles de prix HP et HC.
- Les capteurs de prix HP/HC restent optionnels pour la comptabilité.
- Hiérarchie de démarrage automatique :
  - HP/HC : HC favorable, HP défavorable.
  - Dynamique : démarrage seulement si le prix actuel n'est pas plus mauvais
    que le prochain / la moyenne disponible.
  - un cycle utilisateur/protégé déjà engagé reste prioritaire.
- Nouveaux capteurs par appareil :
  énergie HP, énergie HC et tarif actuel.
- Boiler en Compensation : les contraintes purement énergétiques n'imposent
  plus l'arrêt; sécurités et fallback existants restent actifs.
