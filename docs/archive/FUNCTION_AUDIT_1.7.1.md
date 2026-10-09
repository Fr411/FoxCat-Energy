# FoxCat Energy V1.7.1 — Audit de migration depuis V1.6.160

## Baseline

La baseline est exclusivement `FoxCat-Energy-1.6.160(2).zip` fournie pour cette migration.

## Matrice

| Élément V1.6.160 | Décision V1.7.1 |
|---|---|
| EMS Core | Conservé, étendu avec les dimensions tarifaires indépendantes |
| InverterCore / PRI / RRCR | Conservé ; le Planner ne commande pas le PRI |
| EnergyBus / ACK-NOK | Conservé |
| MachineCycleManager | Conservé ; cycles protégés prioritaires |
| BoilerManager / sécurité 68 °C | Conservé ; Planner seulement décisionnaire économique |
| Load Guard | Conservé |
| Financial Core / Accounting | Conservé |
| Machine Learning | Conservé et utilisé pour profils Planner |
| Métronome | Conservé |
| Registre entités | Conservé et étendu |
| Configuration/Options Flow | Conservé et étendu |
| Diagnostics | Enrichis |
| Dashboard V1.6.160 | Copie originale conservée intacte |
| Dashboard V1.7.1 | Nouvelle version distincte |
| Modes historiques | Migration vers Éco/Confort/Manuel ; régimes tarifaires séparés |

Aucune suppression silencieuse de composant historique n'a été effectuée.
