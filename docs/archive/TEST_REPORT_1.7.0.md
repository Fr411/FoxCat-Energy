# FoxCat Energy 1.7.0 — Rapport de validation

Validation exécutée sur l’archive source finale.

- **OK** — Manifest 1.7.0: version=1.7.0
- **OK** — JSON strings.json: valide
- **OK** — JSON fr.json: valide
- **OK** — YAML homefoxcat_dashboard_client_1.7.0.yaml: views=8
- **OK** — YAML dashboard.yaml: views=8
- **OK** — Une seule vue principale: principale=1, sous-vues=7
- **OK** — Sous-vues officielles: energie, marche, boiler, appareils, onduleur, technique, diagnostic
- **OK** — Nettoyage IA/ML interface: aucun libellé IA/ML
- **OK** — Audit fonctions: 378 → 386 (delta +8)
- **OK** — Sanctuarisé energy_bus.py: 67958102a9362fe519c70f60fa2f2eecb87b4fe90dbbea97f7e390b6c4d531aa
- **OK** — Sanctuarisé machine_cycle.py: 0c3856d4b980d0407570c4f09d2e9d12d97a08c46d49d3909e600fd73e55fc80
- **OK** — Sanctuarisé machine_learning.py: 915520d91c11c4697963788d7ed1ce1f80f6d825b32c83ecff31936ef74c5504
- **OK** — Sanctuarisé accounting/manager.py: 412ae1ebb621cfbc901497c1da491d5b172b3da286780b030a88bf171b6a2726
- **OK** — Sanctuarisé engine/load_guard.py: a0bb7402400d2da9ec5a0997fb7e78bd2fb11dd200de8761c4084745cd56b824
- **OK** — Réglage dynamic_favorable_position_pct: "dynamic_favorable_position_pct": 30.0
- **OK** — Réglage dynamic_high_position_pct: "dynamic_high_position_pct": 65.0
- **OK** — Réglage boiler_temp_boost_c: "boiler_temp_boost_c": 65.0
- **OK** — Réglage boiler_temp_safety_c: "boiler_temp_safety_c": 68.0
- **OK** — Boost solaire prioritaire: branche solaire évaluée avant l’arbitrage contrat
- **OK** — Migration 1.6.x: modes historiques migrés vers comportement/contrat/politique
- **OK** — Wallonie Impact: [(2, 'ECO'), (8, 'MEDIUM'), (12, 'ECO'), (18, 'PIC'), (23, 'MEDIUM')]
- **OK** — Durée du creux Dynamic: calcul fin + minutes restantes présent

## Résultat

**22/22 contrôles OK.**
