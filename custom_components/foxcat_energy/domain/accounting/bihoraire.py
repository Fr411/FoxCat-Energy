"""Contrôles HP/HC en lecture seule, sans recalcul ni double comptage."""
from __future__ import annotations
from typing import Any
from ._validation import KWH_TOLERANCE, horizon_check, number, result

class BihoraireAccounting:
    """Vérifie les invariants physiques et la ventilation HP/HC existante."""
    REGIME = "Bi-horaire HP/HC"
    HORIZONS = ("today", "month", "year", "lifetime")

    def validate(self, accounting_view: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        for horizon in self.HORIZONS:
            e, w = horizon_check(accounting_view, horizon)
            errors.extend(e); warnings.extend(w)
            bucket = accounting_view.get(horizon)
            if not isinstance(bucket, dict):
                continue
            tariff = bucket.get("tariff") or {}
            hphc = tariff.get("hphc") if isinstance(tariff, dict) else None
            if not isinstance(hphc, dict):
                warnings.append(f"{horizon}: ventilation HP/HC absente")
                continue
            hp = hphc.get("HP") if isinstance(hphc.get("HP"), dict) else {}
            hc = hphc.get("HC") if isinstance(hphc.get("HC"), dict) else {}
            for metric, global_key in (("import_kwh", "import_kwh"), ("export_kwh", "export_kwh")):
                split = number(hp.get(metric)) + number(hc.get(metric))
                total = max(number(bucket.get(global_key)), 0.0)
                if split > total + KWH_TOLERANCE:
                    errors.append(f"{horizon}: HP+HC {metric} ({split:.6f}) dépasse le compteur global ({total:.6f})")
            for app_id, app in (bucket.get("appliances") or {}).items():
                if not isinstance(app, dict):
                    continue
                hp_kwh, hc_kwh = number(app.get("hp_kwh")), number(app.get("hc_kwh"))
                energy = max(number(app.get("energy_kwh")), 0.0)
                if hp_kwh < -KWH_TOLERANCE or hc_kwh < -KWH_TOLERANCE:
                    errors.append(f"{horizon}.appliances.{app_id}: kWh HP/HC négatifs")
                if hp_kwh + hc_kwh > energy + KWH_TOLERANCE:
                    errors.append(f"{horizon}.appliances.{app_id}: HP+HC dépasse l'énergie totale")
        return result(self.REGIME, errors, warnings)
