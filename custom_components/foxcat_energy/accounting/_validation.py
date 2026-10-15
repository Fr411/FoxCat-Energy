"""Helpers communs de validation en lecture seule du ledger FoxCat."""
from __future__ import annotations

import math
from typing import Any

KWH_TOLERANCE = 1e-6


def number(value: Any, *, default: float = 0.0) -> float:
    """Convertit un nombre sans masquer NaN/inf dans les validations."""
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def horizon_check(view: dict[str, Any], horizon: str) -> tuple[list[str], list[str]]:
    """Vérifie les compteurs physiques et la cohérence du schéma d'un horizon."""
    errors: list[str] = []
    warnings: list[str] = []
    bucket = view.get(horizon)
    if not isinstance(bucket, dict):
        return [f"{horizon}: horizon absent ou invalide"], warnings

    physical = ("house_kwh", "pv_kwh", "self_consumed_kwh", "export_kwh", "import_kwh")
    for key in physical:
        value = bucket.get(key, 0.0)
        if not finite(value):
            errors.append(f"{horizon}.{key}: valeur non finie ou non numérique")
        elif number(value) < -KWH_TOLERANCE:
            errors.append(f"{horizon}.{key}: compteur physique négatif ({number(value):.9f})")

    # Les montants financiers doivent être finis, mais peuvent légitimement être
    # négatifs (prix d'achat négatif ou coût d'export négatif selon le modèle).
    financial = ("import_cost_eur", "export_value_eur", "export_revenue_eur", "export_cost_eur", "solar_avoided_cost_eur")
    for key in financial:
        if key in bucket and not finite(bucket[key]):
            errors.append(f"{horizon}.{key}: montant non fini ou non numérique")

    tariff = bucket.get("tariff")
    if not isinstance(tariff, dict):
        warnings.append(f"{horizon}: détail tarifaire absent; réconciliation tarifaire impossible")
        return errors, warnings

    tariff_import = 0.0
    tariff_export = 0.0
    for name, rate in (("dynamic", tariff.get("dynamic")), ("HP", (tariff.get("hphc") or {}).get("HP") if isinstance(tariff.get("hphc"), dict) else None), ("HC", (tariff.get("hphc") or {}).get("HC") if isinstance(tariff.get("hphc"), dict) else None), ("other", tariff.get("other"))):
        if not isinstance(rate, dict):
            continue
        for key in ("import_kwh", "export_kwh"):
            value = rate.get(key, 0.0)
            if not finite(value):
                errors.append(f"{horizon}.tariff.{name}.{key}: valeur non finie ou non numérique")
            elif number(value) < -KWH_TOLERANCE:
                errors.append(f"{horizon}.tariff.{name}.{key}: compteur physique négatif")
        tariff_import += max(number(rate.get("import_kwh")), 0.0)
        tariff_export += max(number(rate.get("export_kwh")), 0.0)
        for key in ("import_cost_eur", "export_revenue_eur", "export_cost_eur"):
            if key in rate and not finite(rate[key]):
                errors.append(f"{horizon}.tariff.{name}.{key}: montant non fini ou non numérique")

    total_import = max(number(bucket.get("import_kwh")), 0.0)
    total_export = max(number(bucket.get("export_kwh")), 0.0)
    if tariff_import > total_import + KWH_TOLERANCE:
        errors.append(f"{horizon}: détail tarifaire import ({tariff_import:.6f} kWh) supérieur à l'import physique ({total_import:.6f} kWh)")
    elif total_import - tariff_import > KWH_TOLERANCE:
        # Avertissement plutôt qu'erreur : les anciennes sauvegardes peuvent
        # contenir des compteurs globaux sans ventilation tarifaire complète.
        warnings.append(f"{horizon}: ventilation tarifaire import incomplète ({tariff_import:.6f}/{total_import:.6f} kWh)")
    if tariff_export > total_export + KWH_TOLERANCE:
        errors.append(f"{horizon}: détail tarifaire export ({tariff_export:.6f} kWh) supérieur à l'export physique ({total_export:.6f} kWh)")
    elif total_export - tariff_export > KWH_TOLERANCE:
        warnings.append(f"{horizon}: ventilation tarifaire export incomplète ({tariff_export:.6f}/{total_export:.6f} kWh)")

    appliances = bucket.get("appliances")
    if isinstance(appliances, dict):
        for aid, app in appliances.items():
            if not isinstance(app, dict):
                errors.append(f"{horizon}.appliances.{aid}: entrée invalide")
                continue
            energy = number(app.get("energy_kwh"))
            solar = number(app.get("solar_kwh"))
            grid = number(app.get("grid_kwh"))
            if any(not finite(app.get(key, 0.0)) for key in ("energy_kwh", "solar_kwh", "grid_kwh", "cost_eur")):
                errors.append(f"{horizon}.appliances.{aid}: énergie ou coût non fini/non numérique")
            if min(energy, solar, grid) < -KWH_TOLERANCE:
                errors.append(f"{horizon}.appliances.{aid}: compteur physique négatif")
            if solar + grid > energy + KWH_TOLERANCE:
                errors.append(f"{horizon}.appliances.{aid}: solaire + réseau dépasse l'énergie totale")
            elif energy - solar - grid > KWH_TOLERANCE:
                warnings.append(f"{horizon}.appliances.{aid}: énergie non ventilée entre solaire et réseau")
    return errors, warnings


def result(regime: str, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    return {"status": "error" if errors else "warning" if warnings else "ok", "regime": regime, "errors": errors, "warnings": warnings}
