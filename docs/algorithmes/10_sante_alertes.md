# 10 · Santé et alertes de panne

Une alerte signale une panne qui empêche FoxCat de fonctionner ou compromet la sécurité. Code : `domain/health.py` (pur, testé), branché dans `runtime/coordinator.py` (`_health_inputs`, `_health_view`, `_sync_health_notifications`).

## Catalogue des pannes

| Code | Gravité | Condition | Délai |
|---|---|---|---|
| `EMS_AVEUGLE` | **Critique** | régulation active, pas en Manuel, instantané invalide ou métronome `PERDU` | 2 min |
| `BOILER_SURCHAUFFE` | **Critique** | température de sécurité ≥ limite (68 °C), **même en Manuel** | immédiat |
| `BOILER_SONDE_SECURITE_HS` | **Critique** | ni sonde boiler ni sonde résistance lisibles : FoxCat lit 0 °C | 2 min |
| `BOILER_SONDE_HS` | **Critique** | sonde boiler illisible (la sonde de sécurité répond) | 2 min |
| `PRI_ILLISIBLE` | **Critique** | PRI activé et relais RRCR indisponibles (`????`) | 2 min |
| `ACTIONNEUR_ECHEC` | **Critique** | statut d'exécution `FAILED` ou `TIMEOUT` | 2 min |
| `METRONOME_SECOURS` | Majeure | métronome sur le capteur de secours | 2 min |
| `PRIX_INDISPONIBLES` | Majeure | flux de prix `DEGRADE` (tampon épuisé) | 2 min |
| `INTERNET_COUPE` | Majeure | Internet coupé (indique si le Backup est actif) | 2 min |
| `MACHINE_INDISPONIBLE` | Majeure | prise d'une machine `unavailable` | 2 min |
| `DELESTAGE_ACTIF` | Majeure | délestage du disjoncteur en cours | immédiat |
| `CONFLIT_AUTOMATISATION` | Majeure | ancienne automatisation FoxCat active | 2 min |
| `FOXCAT_EN_ERREUR` | Majeure | dernière mise à jour du coordinateur en échec | 2 min |
| `ENTITE_INTROUVABLE` | Majeure | une entité essentielle configurée n'existe plus | 2 min |

Les alertes du boiler et du PRI ne se déclenchent pas en mode Manuel, régulation coupée ou boiler non géré : FoxCat ne pilote alors rien. La surchauffe fait exception, c'est une sécurité du matériel.

## Temporisation (`AlertTracker`)

Une alerte devient visible après son délai (2 minutes, sauf surchauffe et délestage), et n'est levée qu'après **60 secondes** de retour stable. Une panne plus courte que le délai ne notifie jamais ; un va-et-vient ne renotifie pas.

## Sorties

- **Capteur « Santé FoxCat (alertes de panne) »** : `OK`, `MAJEUR` ou `CRITIQUE`, avec les attributs `alertes` (code, gravité, titre, détail, depuis), `nombre_alertes`, `critiques`, `majeures`.
- **Capteur binaire « Alerte de panne FoxCat »** (problème) : allumé dès qu'une alerte est visible.
- **Notification persistante** (cloche de Home Assistant), une par alerte, retirée quand la panne est levée.
- **Événement `foxcat_energy_alert`** (`state` : `raised` ou `cleared`, `code`, `severity`, `title`, `detail`, `installation`) pour les automatisations. Exemple de notification sur téléphone : `docs/automations/alerte_panne_foxcat.yaml`.
- Interrupteur **« Alertes de panne FoxCat (notifications) »** : coupe les notifications et les événements ; les capteurs restent.

## Ce que les alertes ne détectent pas

Les défauts de logique du code (voir `ANOMALIES.md`) ne se voient pas à l'exécution. Une décision mauvaise mais sans panne (prix aberrant, réglage erroné) ne déclenche rien.
