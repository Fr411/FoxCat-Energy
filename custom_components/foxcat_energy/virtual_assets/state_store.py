"""Persistance et reprise sécurisée des états simulés (Virtual Assets Core)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .const import ALGORITHM_VERSION, SCHEMA_VERSION
from .shadow import ShadowSimulator

MAX_EXPECTED_GAP_SECONDS = 900.0


class VirtualAssetsStateStore:
    """Gère la sérialisation, la reprise et la continuité temporelle du ShadowSimulator."""

    def __init__(self) -> None:
        self.last_processed_ts: datetime | None = None
        self.gaps_detected: int = 0
        self.last_gap_seconds: float = 0.0
        self.duplicates_ignored: int = 0
        self.out_of_order_ignored: int = 0
        self.restored: bool = False

    def check_and_advance_timestamp(
        self, current_ts: datetime, max_step_s: float = 300.0
    ) -> tuple[bool, float, str]:
        if self.last_processed_ts is None:
            self.last_processed_ts = current_ts
            return True, 0.0, "initial_step"

        delta_s = (current_ts - self.last_processed_ts).total_seconds()
        if delta_s == 0:
            self.duplicates_ignored += 1
            return False, 0.0, "duplicate_timestamp"
        if delta_s < 0:
            self.out_of_order_ignored += 1
            return False, 0.0, "out_of_order_timestamp"

        self.last_processed_ts = current_ts
        if delta_s > MAX_EXPECTED_GAP_SECONDS:
            self.gaps_detected += 1
            self.last_gap_seconds = round(delta_s, 1)
            return True, min(delta_s, max_step_s) / 3600.0, "gap_detected_capped_step"

        return True, delta_s / 3600.0, "ok"

    def dump(self, shadow: ShadowSimulator | None) -> dict[str, Any]:
        if shadow is None:
            return {
                "schema_version": SCHEMA_VERSION,
                "algorithm_version": ALGORITHM_VERSION,
                "active": False,
            }
        car = shadow._tracker.car
        return {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "active": True,
            "last_processed_ts": self.last_processed_ts.isoformat() if self.last_processed_ts else None,
            "gaps_detected": self.gaps_detected,
            "last_gap_seconds": self.last_gap_seconds,
            "duplicates_ignored": self.duplicates_ignored,
            "out_of_order_ignored": self.out_of_order_ignored,
            "battery": {
                "soc_kwh": round(shadow.battery.soc_kwh, 6),
                "charged_cell_kwh": round(shadow.battery.charged_cell_kwh, 6),
                "discharged_cell_kwh": round(shadow.battery.discharged_cell_kwh, 6),
            },
            "ev": {
                "soc_kwh": round(car.soc_kwh, 6) if car is not None else 0.0,
            },
            "real_totals": dict(shadow.real_totals),
            "skipped": shadow.skipped,
            "ledger": {
                "scenario": shadow.ledger.scenario,
                "baseline": shadow.ledger.baseline,
                "battery_charge_kwh": shadow.ledger.battery_charge_kwh,
                "battery_discharge_kwh": shadow.ledger.battery_discharge_kwh,
                "battery_loss_kwh": shadow.ledger.battery_loss_kwh,
                "ev_kwh": shadow.ledger.ev_kwh,
                "slots": shadow.ledger.slots,
            },
        }

    def restore(self, raw: Any, shadow: ShadowSimulator | None) -> bool:
        if not isinstance(raw, dict) or shadow is None:
            return False
        if raw.get("schema_version") != SCHEMA_VERSION or not raw.get("active"):
            return False
        try:
            ts_raw = raw.get("last_processed_ts")
            if isinstance(ts_raw, str) and ts_raw:
                self.last_processed_ts = datetime.fromisoformat(ts_raw)
            self.gaps_detected = int(raw.get("gaps_detected", 0))
            self.last_gap_seconds = float(raw.get("last_gap_seconds", 0.0))
            self.duplicates_ignored = int(raw.get("duplicates_ignored", 0))
            self.out_of_order_ignored = int(raw.get("out_of_order_ignored", 0))

            bat_raw = raw.get("battery")
            if isinstance(bat_raw, dict):
                soc_kwh = float(bat_raw.get("soc_kwh", shadow.battery.soc_kwh))
                shadow.battery.soc_kwh = max(
                    shadow.battery.min_kwh, min(shadow.battery.max_kwh, soc_kwh)
                )
                shadow.battery.charged_cell_kwh = max(0.0, float(bat_raw.get("charged_cell_kwh", 0.0)))
                shadow.battery.discharged_cell_kwh = max(0.0, float(bat_raw.get("discharged_cell_kwh", 0.0)))

            ev_raw = raw.get("ev")
            if isinstance(ev_raw, dict) and shadow._tracker.car is not None:
                ev_soc = float(ev_raw.get("soc_kwh", 0.0))
                shadow._tracker.car.soc_kwh = max(
                    0.0, min(shadow._tracker.car.spec.capacity_kwh, ev_soc)
                )

            real_raw = raw.get("real_totals")
            if isinstance(real_raw, dict):
                shadow.real_totals["load_kwh"] = float(real_raw.get("load_kwh", 0.0))
                shadow.real_totals["pv_kwh"] = float(real_raw.get("pv_kwh", 0.0))
                shadow.real_totals["slots"] = int(real_raw.get("slots", 0))

            shadow.skipped = int(raw.get("skipped", 0))

            ledger_raw = raw.get("ledger")
            if isinstance(ledger_raw, dict):
                if isinstance(ledger_raw.get("scenario"), dict):
                    for k, v in ledger_raw["scenario"].items():
                        if k in shadow.ledger.scenario and isinstance(v, dict):
                            shadow.ledger.scenario[k].update(v)
                if isinstance(ledger_raw.get("baseline"), dict):
                    for k, v in ledger_raw["baseline"].items():
                        if k in shadow.ledger.baseline and isinstance(v, dict):
                            shadow.ledger.baseline[k].update(v)
                shadow.ledger.battery_charge_kwh = float(ledger_raw.get("battery_charge_kwh", 0.0))
                shadow.ledger.battery_discharge_kwh = float(ledger_raw.get("battery_discharge_kwh", 0.0))
                shadow.ledger.battery_loss_kwh = float(ledger_raw.get("battery_loss_kwh", 0.0))
                shadow.ledger.ev_kwh = float(ledger_raw.get("ev_kwh", 0.0))
                shadow.ledger.slots = int(ledger_raw.get("slots", 0))

            self.restored = True
            return True
        except (TypeError, ValueError, KeyError):
            return False
