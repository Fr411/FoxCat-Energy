"""Hooks Home Assistant en lecture seule.

Aucun import de Home Assistant au niveau module et aucun appel de service : le module ne
fait que lire ``hass.states`` pour des capteurs de mesure.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .config import VirtualAssetsConfig, config_from_settings
from .const import describe_reasons, map_official_reasons
from .diagnostics import build_diagnostics
from .input_adapter import build_forecast_slots, build_slot_from_snapshot
from .profitability import ProfitabilityInputs, analyze_profitability
from .shadow import ShadowSimulator
from .state_store import VirtualAssetsStateStore


def read_float_state(hass: Any, entity_id: str | None) -> float | None:
    """Lit un capteur ; ``None`` si absent, ``unknown``/``unavailable`` ou non numérique."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


class VirtualAssetsRuntime:
    """Conteneur d'exécution ; ``shadow`` vaut ``None`` tant que le module est désactivé."""

    def __init__(self, config: VirtualAssetsConfig) -> None:
        self.config = config
        self.store = VirtualAssetsStateStore()
        self.shadow: ShadowSimulator | None = (
            ShadowSimulator(config) if config.enabled and config.shadow_mode else None
        )
        self.last_status: str = "IDLE"

    def reconfigure(self, settings: Mapping[str, Any] | None) -> None:
        saved = self.dump_state() if self.shadow is not None else None
        self.config = config_from_settings(settings)
        if self.config.enabled and self.config.shadow_mode:
            self.shadow = ShadowSimulator(self.config)
            if saved:
                self.store.restore(saved, self.shadow)
        else:
            self.shadow = None

    def observe_snapshot(
        self,
        *,
        timestamp: datetime,
        house_w: float | None,
        pv_w: float | None,
        prices: Mapping[str, Any],
        settings: Mapping[str, Any],
        import_points: tuple[Any, ...] | list[Any] = (),
        export_points: tuple[Any, ...] | list[Any] = (),
    ) -> bool:
        if not self.config.enabled or self.shadow is None:
            return False

        valid, dt_hours, reason = self.store.check_and_advance_timestamp(timestamp)
        self.last_status = reason
        if not valid or dt_hours <= 0.0:
            return False

        slot = build_slot_from_snapshot(
            timestamp=timestamp,
            dt_hours=dt_hours,
            house_w=house_w,
            pv_w=pv_w,
            prices=prices,
            settings=settings,
        )
        if slot is None:
            return False

        forecast = build_forecast_slots(
            now=timestamp,
            import_points=import_points,
            export_points=export_points,
            settings=settings,
            expected_house_w=house_w if isinstance(house_w, (int, float)) and house_w > 0 else 500.0,
        )
        self.shadow.observe(slot, forecast)
        return True

    def dump_state(self) -> dict[str, Any]:
        return self.store.dump(self.shadow)

    def restore_state(self, raw: Any) -> bool:
        return self.store.restore(raw, self.shadow)

    def view(self) -> dict[str, Any]:
        if not self.config.enabled or self.shadow is None:
            return {
                "enabled": self.config.enabled,
                "mode": "shadow" if self.config.shadow_mode else "counterfactual",
                "status_label": "DÉSACTIVÉ",
                "data_badge": "DONNÉE MANQUANTE",
                "battery_soc_pct": None,
                "battery_soc_kwh": None,
                "battery_cycles": 0.0,
                "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0,
                "battery_loss_kwh": 0.0,
                "ev_soc_kwh": None,
                "ev_charge_kwh": 0.0,
                "savings_eur": 0.0,
                "estimated_savings_eur": 0.0,
                "last_action": "idle",
                "last_reason_codes": [],
                "last_reason_description": "Module désactivé",
                "gaps_detected": self.store.gaps_detected,
                "profitability": {"quality": "estimated", "payback_years": None, "npv_eur": None},
            }

        snap = self.shadow.snapshot()
        sim = snap["simulated"]
        acc = snap["accounting"]
        raw_reasons = sim.get("last_reasons") or []
        official_codes = map_official_reasons(raw_reasons)
        badge = "SIMULÉ" if self.shadow.ledger.slots > 0 else "ESTIMÉ"

        total_hours = self.shadow.real_totals.get("slots", 0) * (5.0 / 3600.0)
        period_days = max(total_hours / 24.0, 0.001) if self.shadow.ledger.slots > 0 else None
        prof = analyze_profitability(
            ProfitabilityInputs(
                savings_eur=acc.get("savings_eur", 0.0),
                period_days=period_days,
                capex_eur=self.config.battery.capex_eur,
                degradation_pct_per_year=self.config.battery.degradation_pct_per_year,
            )
        )

        return {
            "enabled": True,
            "mode": "shadow" if self.config.shadow_mode else "counterfactual",
            "status_label": f"ACTIF ({badge}) • LECTURE SEULE",
            "data_badge": badge,
            "battery_soc_pct": sim.get("battery_soc_pct"),
            "battery_soc_kwh": round(self.shadow.battery.soc_kwh, 3),
            "battery_cycles": sim.get("battery_cycles", 0.0),
            "battery_charge_kwh": round(acc.get("battery_charge_kwh", 0.0), 4),
            "battery_discharge_kwh": round(acc.get("battery_discharge_kwh", 0.0), 4),
            "battery_loss_kwh": round(acc.get("battery_loss_kwh", 0.0), 4),
            "ev_soc_kwh": sim.get("ev_soc_kwh"),
            "ev_charge_kwh": round(acc.get("ev_kwh", 0.0), 4),
            "savings_eur": round(acc.get("savings_eur", 0.0), 4),
            "estimated_savings_eur": round(acc.get("savings_estimated_eur", 0.0), 4),
            "unpriced_slots": acc.get("unpriced_slots", 0),
            "skipped_slots": snap.get("skipped_slots", 0),
            "gaps_detected": self.store.gaps_detected,
            "last_action": sim.get("last_action") or "idle",
            "last_reason_codes": official_codes,
            "last_reason_description": describe_reasons(official_codes),
            "profitability": prof,
        }

    def diagnostics(self) -> dict[str, Any]:
        return build_diagnostics(
            self.config, None if self.shadow is None else self.shadow.snapshot()
        )

    def unload(self) -> None:
        self.shadow = None


def setup_virtual_assets(settings: Mapping[str, Any] | None) -> VirtualAssetsRuntime:
    return VirtualAssetsRuntime(config_from_settings(settings))
