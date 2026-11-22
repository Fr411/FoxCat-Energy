# Journal des versions FoxCat Energy

Une ligne par version : version, date, résumé en une phrase, lien vers la pull request. Le détail complet reste dans [`CHANGELOG.md`](CHANGELOG.md). Les anomalies d'algorithmes sont suivies dans [`docs/algorithmes/ANOMALIES.md`](docs/algorithmes/ANOMALIES.md).

| Version | Date | Résumé | Pull request |
|---|---|---|---|
| Dashboards 1.8.0 | 2026-11-22 | Dashboards tablette/PC et mobile livrés à l'installation (vue Flux avec Mina, Boiler animé, Machines, Chauffage, Délestage haute consommation) ; carte Délestage alimentée par les valeurs réelles du délestage. | [#79](https://github.com/Fr411/FoxCat-Energy/pull/79) |
| 1.7.6 (non publiée) | 2026-11-20 | Mode Backup (Internet coupé), alertes de panne, tampon local des prix, corrections A-30, A-32, A-33, A-35 ; capteur « Période tarifaire » en double retiré et lectures de fichiers sorties de la boucle d'événements ; ACK LOGO et disponibilité de la commande onduleur (retour réel des relais RRCR) avec garde PRI et champ « LOGO en ligne » si le LOGO est indisponible. | [#70](https://github.com/Fr411/FoxCat-Energy/pull/70), [#71](https://github.com/Fr411/FoxCat-Energy/pull/71), [#72](https://github.com/Fr411/FoxCat-Energy/pull/72), [#74](https://github.com/Fr411/FoxCat-Energy/pull/74), [#76](https://github.com/Fr411/FoxCat-Energy/pull/76), [#77](https://github.com/Fr411/FoxCat-Energy/pull/77) |
| 1.7.5 | — | Non documentée dans le dépôt. | — |
| 1.7.4 (préparation) | — | Sauvegarde du dashboard utilisateur et fusion prudente des personnalisations. | — |
| 1.7.3 (préparation) | — | Sélections harmonisées, commandes des appareils, configurateur Technique et profils, découverte des versions de dashboard. | — |
| 1.7.2 | — | Corrections du chargement des réglages et du dispatch dynamique, Price Analyzer enrichi. | — |
| 1.7.1 | — | Migration tarifaire indépendante, Price Analyzer V2, Flexible Load Planner, dashboard versionné. | — |
| 1.6.160 | — | Base fournie par l'utilisateur. | — |

Les lignes de 1.7.4 à 1.6.160 viennent de l'ancien journal ([`trash/JOURNAL_VERSIONS.md`](trash/JOURNAL_VERSIONS.md)) ; leurs dates et pull requests n'ont pas été retrouvées.
