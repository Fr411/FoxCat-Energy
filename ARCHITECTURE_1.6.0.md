# Architecture FoxCat Energy 1.6.0

```text
Puissance réseau signée ─┐
                         ├─> Sources énergétiques
Production PV ───────────┘          │
                                    ▼
                          Modèle énergétique FoxCat
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
              Énergie           Onduleur             EMS
                  │                 │                 │
                  └─────────────────┼─────────────────┘
                                    ▼
                               Energy Bus
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
               Machines           Boiler        Tarification
                                    │
                                    ▼
                               Métronome
                                    │
                                    ▼
                               Diagnostic
```

## Invariants

- Deux sources énergétiques physiques obligatoires seulement.
- Convention normalisée par défaut : réseau `+` = prélèvement, `−` = réinjection.
- `consommation_maison = production_pv + prélèvement - réinjection`.
- Le fallback réseau est une seconde mesure signée et remplace ensemble valeur + cadence.
- Les cartes du dashboard utilisent des rôles du registre FoxCat, jamais des `entity_id` natifs en dur dans le modèle.
- L'ordre fonctionnel officiel est immuable et défini dans `const.py`.
- PRI désigne le moteur interne; l'interface utilisateur présente le module sous le nom **Onduleur**.
