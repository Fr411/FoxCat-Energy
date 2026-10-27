"""Contrôles de cohérence pour la tarification dynamique Day-Ahead."""
from __future__ import annotations
from typing import Any
from ._validation import KWH_TOLERANCE, horizon_check, number, result

class DynamicAccounting:
    """Vérifie la ventilation dynamique sans recalculer les coûts historiques."""
    REGIME = "Dynamique"
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
            tariff = bucket.get("tariff") if isinstance(bucket.get("tariff"), dict) else {}
            dynamic = tariff.get("dynamic") if isinstance(tariff.get("dynamic"), dict) else {}
            for metric in ("import_kwh", "export_kwh"):
                value = number(dynamic.get(metric))
                total = max(number(bucket.get(metric)), 0.0)
                if value > total + KWH_TOLERANCE:
                    errors.append(f"{horizon}: dynamic.{metric} dépasse le compteur physique global")
            for app_id, app in (bucket.get("appliances") or {}).items():
                if not isinstance(app, dict):
                    continue
                value = number(app.get("dynamic_kwh"))
                energy = max(number(app.get("energy_kwh")), 0.0)
                if value < -KWH_TOLERANCE or value > energy + KWH_TOLERANCE:
                    errors.append(f"{horizon}.appliances.{app_id}: kWh dynamiques hors limites de l'énergie totale")
        return result(self.REGIME, errors, warnings)
