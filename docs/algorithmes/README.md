# Algorithmes de fonctionnement de FoxCat Energy

Audit complet du code (V1.7.6) : chaque algorithme est décrit pas à pas (entrées, étapes, seuils par défaut, sécurités, cas limites, tests existants), avec le fichier source en tête de page.

| Page | Contenu |
|---|---|
| [01 · Boucle EMS](01_boucle_ems.md) | métronome, instantané, trames, EMS Core, machine à états, bus d'énergie, commande et vérification du boiler |
| [02 · Boiler et modes](02_boiler_et_modes.md) | Éco / Confort / Manuel, boiler dynamique, modèle thermique, modules inatteignables |
| [03 · Onduleur PRI / RRCR](03_pri_onduleur.md) | décision prédictive, actionneur, ACK, fin de journée solaire |
| [04 · Tarification](04_tarification.md) | deux axes contrat × réseau, prix actif, comparateur, coûts réseau |
| [05 · Prix dynamiques](05_prix_dynamiques.md) | séries de prix, Price Analyzer, décision économique, planificateur Day-Ahead |
| [06 · Comptabilité](06_comptabilite.md) | ledger, ventilation tarifaire, appareils, économies FoxCat, série au quart d'heure |
| [07 · Machines et planificateur](07_machines_planificateur.md) | fenêtres, cycles protégés, réconciliation, apprentissage, planificateur |
| [08 · Protection et chauffage](08_protection_chauffage.md) | délestage, tensions et déséquilibre, décalage de consigne, PAC |
| [09 · Batterie, VPP, IA, infrastructure](09_batterie_vpp_infra.md) | simulation, V2H, IA solaire, profils, migration, dashboards |
| [**Anomalies**](ANOMALIES.md) | **28 écarts relevés**, gravité, preuves, propositions et tests à ajouter |

**Méthode** : lecture du code source, puis vérification par de petits calculs exécutés quand c'était possible (points marqués ✔ dans le rapport). Rien n'a été essayé dans Home Assistant. L'audit n'a **rien corrigé**.

Les identifiants `A-xx` des pages renvoient au rapport d'anomalies.
