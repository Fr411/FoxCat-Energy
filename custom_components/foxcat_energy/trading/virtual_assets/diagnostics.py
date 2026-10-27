"""Diagnostics du module : liste blanche, sans chemin de contrôle ni commande physique."""
from __future__ import annotations

from typing import Any

from .config import VirtualAssetsConfig

_FORBIDDEN = ("entity_id", "service", "command", "switch", "script", "automation", "token")


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()
                if not any(f in str(k).lower() for f in _FORBIDDEN)}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def build_diagnostics(config: VirtualAssetsConfig, shadow_snapshot: dict[str, Any] | None = None
                      ) -> dict[str, Any]:
    """Lecture seule, quelles que soient les entrées ; clés suspectes retirées."""
    data: dict[str, Any] = {
        "enabled": config.enabled,
        "mode": "shadow" if config.shadow_mode else "counterfactual_only",
        "controls_physical_devices": False,
        "battery": {"capacity_kwh": config.battery.capacity_kwh,
                    "reserve_soc_pct": config.battery.reserve_soc_pct},
        "ev": None if config.ev is None else {"capacity_kwh": config.ev.capacity_kwh},
        "data_quality_legend": ["measured", "simulated", "estimated", "missing"],
    }
    if config.enabled and shadow_snapshot is not None:
        data["shadow"] = _clean(shadow_snapshot)
    return data
