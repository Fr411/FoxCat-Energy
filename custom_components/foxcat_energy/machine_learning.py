from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


class MachineLearningRecorder:
    """Collecte passive de signatures électriques des machines.

    Cette classe n'influence jamais l'EMS, le PRI, Energy Bus ni la machine à
    états des cycles. Elle observe uniquement les télémétries disponibles afin
    de constituer un historique local utilisable plus tard pour l'apprentissage.
    """

    MAX_CYCLES_PER_MACHINE = 30
    MAX_POINTS_PER_CYCLE = 720
    MIN_POINT_INTERVAL_S = 10.0
    MAX_INTEGRATION_GAP_S = 120.0
    PERIODIC_SAVE_S = 300.0

    def __init__(self) -> None:
        self._machines: dict[str, dict[str, Any]] = {}
        self._last_save_at: datetime | None = None

    def restore(self, raw: Any) -> None:
        """Restaure uniquement l'historique terminé.

        Un cycle en cours n'est volontairement jamais repris après un restart
        Home Assistant afin d'éviter d'intégrer le temps d'arrêt comme énergie.
        """
        if not isinstance(raw, dict):
            return
        machines = raw.get("machines")
        if not isinstance(machines, dict):
            return
        for machine_id, value in machines.items():
            if not isinstance(value, dict):
                continue
            cycles = value.get("cycles")
            if not isinstance(cycles, list):
                cycles = []
            self._machines[str(machine_id)] = {
                "name": str(value.get("name") or machine_id),
                "total_cycles": int(value.get("total_cycles", len(cycles)) or 0),
                "cycles": cycles[-self.MAX_CYCLES_PER_MACHINE :],
                "current": None,
                "candidate_at": None,
                "low_since": None,
                "last_observation": None,
            }

    def dump(self) -> dict[str, Any]:
        machines: dict[str, Any] = {}
        for machine_id, rec in self._machines.items():
            machines[machine_id] = {
                "name": rec.get("name", machine_id),
                "total_cycles": int(rec.get("total_cycles", 0)),
                "cycles": deepcopy(rec.get("cycles", []))[-self.MAX_CYCLES_PER_MACHINE :],
            }
        return {"machines": machines}

    def observe(
        self,
        *,
        machine_id: str,
        name: str,
        now: datetime,
        power_w: float | None,
        current_a: float | None,
        voltage_v: float | None,
        switch_on: bool,
        cycle_state: str,
        cycle_origin: str,
        cycle_protected: bool,
        start_w: float,
        end_w: float,
        end_confirm_s: float,
        context: dict[str, Any] | None = None,
        source: str = "TELEMETRY",
    ) -> bool:
        """Enregistre une observation et retourne True si une sauvegarde est souhaitée."""
        machine_id = str(machine_id)
        rec = self._machines.setdefault(
            machine_id,
            {
                "name": str(name),
                "total_cycles": 0,
                "cycles": [],
                "current": None,
                "candidate_at": None,
                "low_since": None,
                "last_observation": None,
            },
        )
        rec["name"] = str(name)

        power = max(float(power_w or 0.0), 0.0)
        current = float(current_a) if isinstance(current_a, (int, float)) else None
        voltage = float(voltage_v) if isinstance(voltage_v, (int, float)) else None
        start_threshold = max(float(start_w), 0.5)
        end_threshold = max(float(end_w), 0.0)
        end_confirm = max(float(end_confirm_s), 30.0)

        active_signal = bool(cycle_protected or power >= start_threshold)
        current_cycle = rec.get("current")

        if current_cycle is None:
            if not active_signal:
                rec["candidate_at"] = None
                rec["last_observation"] = now.isoformat()
                return self._save_due(now)
            current_cycle = self._new_cycle(
                now=now,
                power_w=power,
                current_a=current,
                voltage_v=voltage,
                switch_on=switch_on,
                cycle_state=cycle_state,
                cycle_origin=cycle_origin,
                context=context or {},
                source=source,
            )
            rec["current"] = current_cycle
            rec["candidate_at"] = None
            rec["low_since"] = None

        self._integrate(current_cycle, now, power)
        self._append_point(
            current_cycle,
            now=now,
            power_w=power,
            current_a=current,
            voltage_v=voltage,
            switch_on=switch_on,
            cycle_state=cycle_state,
            cycle_origin=cycle_origin,
            context=context or {},
            source=source,
        )

        # Détection de fin uniquement pour la collecte. Elle n'agit jamais sur
        # MachineCycleManager ni sur une prise. Le délai reprend le seuil de fin
        # configuré de la machine pour conserver les longues pauses normales.
        if power <= end_threshold and not cycle_protected:
            low_since = rec.get("low_since")
            if low_since is None:
                rec["low_since"] = now
            elif isinstance(low_since, datetime) and (now - low_since).total_seconds() >= end_confirm:
                self._finish_cycle(rec, now, context or {})
                rec["last_observation"] = now.isoformat()
                self._last_save_at = now
                return True
        else:
            rec["low_since"] = None

        rec["last_observation"] = now.isoformat()
        return self._save_due(now)

    def _save_due(self, now: datetime) -> bool:
        if self._last_save_at is None:
            self._last_save_at = now
            return False
        if (now - self._last_save_at).total_seconds() >= self.PERIODIC_SAVE_S:
            self._last_save_at = now
            return True
        return False

    @staticmethod
    def _new_cycle(
        *,
        now: datetime,
        power_w: float,
        current_a: float | None,
        voltage_v: float | None,
        switch_on: bool,
        cycle_state: str,
        cycle_origin: str,
        context: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        return {
            "started_at": now.isoformat(),
            "ended_at": None,
            "duration_s": 0.0,
            "energy_wh": 0.0,
            "samples": 0,
            "max_power_w": power_w,
            "max_current_a": current_a,
            "min_voltage_v": voltage_v,
            "max_voltage_v": voltage_v,
            "origin": str(cycle_origin or "UNKNOWN"),
            "start_context": deepcopy(context),
            "end_context": {},
            "points": [],
            "_last_at": now,
            "_last_power_w": power_w,
            "_last_point_at": None,
            "_last_point_power_w": None,
            "_last_point_switch_on": switch_on,
            "_last_point_cycle_state": cycle_state,
            "_source": source,
        }

    def _integrate(self, cycle: dict[str, Any], now: datetime, power_w: float) -> None:
        last_at = cycle.get("_last_at")
        last_power = float(cycle.get("_last_power_w", power_w) or 0.0)
        if isinstance(last_at, datetime):
            dt_s = (now - last_at).total_seconds()
            if 0 < dt_s <= self.MAX_INTEGRATION_GAP_S:
                cycle["energy_wh"] = float(cycle.get("energy_wh", 0.0)) + ((last_power + power_w) / 2.0) * dt_s / 3600.0
        cycle["_last_at"] = now
        cycle["_last_power_w"] = power_w
        cycle["max_power_w"] = max(float(cycle.get("max_power_w", 0.0)), power_w)

    def _append_point(
        self,
        cycle: dict[str, Any],
        *,
        now: datetime,
        power_w: float,
        current_a: float | None,
        voltage_v: float | None,
        switch_on: bool,
        cycle_state: str,
        cycle_origin: str,
        context: dict[str, Any],
        source: str,
    ) -> None:
        last_point_at = cycle.get("_last_point_at")
        last_power = cycle.get("_last_point_power_w")
        last_switch = cycle.get("_last_point_switch_on")
        last_state = cycle.get("_last_point_cycle_state")
        due = not isinstance(last_point_at, datetime) or (now - last_point_at).total_seconds() >= self.MIN_POINT_INTERVAL_S
        changed = (
            last_power is None
            or abs(float(last_power) - power_w) >= 50.0
            or bool(last_switch) != bool(switch_on)
            or str(last_state) != str(cycle_state)
        )
        if not (due or changed):
            return

        started = datetime.fromisoformat(str(cycle["started_at"]))
        point = {
            "t_s": round(max((now - started).total_seconds(), 0.0), 1),
            "p_w": round(power_w, 1),
            "a": round(current_a, 3) if current_a is not None else None,
            "v": round(voltage_v, 2) if voltage_v is not None else None,
            "sw": bool(switch_on),
            "cycle": str(cycle_state),
            "origin": str(cycle_origin or "UNKNOWN"),
            "grid_w": self._num(context.get("grid_w")),
            "pv_w": self._num(context.get("pv_w")),
            "house_w": self._num(context.get("house_w")),
            "price": self._num(context.get("price"), digits=5),
            "tariff": context.get("tariff"),
            "source": str(source),
        }
        cycle.setdefault("points", []).append(point)
        cycle["samples"] = int(cycle.get("samples", 0)) + 1
        if current_a is not None:
            previous = cycle.get("max_current_a")
            cycle["max_current_a"] = current_a if previous is None else max(float(previous), current_a)
        if voltage_v is not None:
            min_v = cycle.get("min_voltage_v")
            max_v = cycle.get("max_voltage_v")
            cycle["min_voltage_v"] = voltage_v if min_v is None else min(float(min_v), voltage_v)
            cycle["max_voltage_v"] = voltage_v if max_v is None else max(float(max_v), voltage_v)

        cycle["_last_point_at"] = now
        cycle["_last_point_power_w"] = power_w
        cycle["_last_point_switch_on"] = bool(switch_on)
        cycle["_last_point_cycle_state"] = str(cycle_state)
        if len(cycle["points"]) > self.MAX_POINTS_PER_CYCLE:
            cycle["points"] = self._compact_points(cycle["points"])

    @staticmethod
    def _compact_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(points) <= 2:
            return points
        # Garde le premier, le dernier et un point sur deux au milieu.
        compact = [points[0], *points[1:-1:2], points[-1]]
        return compact

    def _finish_cycle(self, rec: dict[str, Any], now: datetime, context: dict[str, Any]) -> None:
        cycle = rec.get("current")
        if not isinstance(cycle, dict):
            return
        started = datetime.fromisoformat(str(cycle["started_at"]))
        cycle["ended_at"] = now.isoformat()
        cycle["duration_s"] = round(max((now - started).total_seconds(), 0.0), 1)
        cycle["energy_wh"] = round(float(cycle.get("energy_wh", 0.0)), 3)
        cycle["max_power_w"] = round(float(cycle.get("max_power_w", 0.0)), 1)
        if cycle.get("max_current_a") is not None:
            cycle["max_current_a"] = round(float(cycle["max_current_a"]), 3)
        if cycle.get("min_voltage_v") is not None:
            cycle["min_voltage_v"] = round(float(cycle["min_voltage_v"]), 2)
        if cycle.get("max_voltage_v") is not None:
            cycle["max_voltage_v"] = round(float(cycle["max_voltage_v"]), 2)
        cycle["end_context"] = deepcopy(context)

        for key in [k for k in cycle if k.startswith("_")]:
            cycle.pop(key, None)
        rec.setdefault("cycles", []).append(cycle)
        rec["cycles"] = rec["cycles"][-self.MAX_CYCLES_PER_MACHINE :]
        rec["total_cycles"] = int(rec.get("total_cycles", 0)) + 1
        rec["current"] = None
        rec["candidate_at"] = None
        rec["low_since"] = None

    def view(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for machine_id, rec in self._machines.items():
            cycles = rec.get("cycles", [])
            recent = cycles[-10:] if isinstance(cycles, list) else []
            durations = [float(c.get("duration_s", 0.0)) for c in recent if float(c.get("duration_s", 0.0)) > 0]
            energies = [float(c.get("energy_wh", 0.0)) for c in recent if float(c.get("energy_wh", 0.0)) >= 0]
            current = rec.get("current")
            current_view = None
            if isinstance(current, dict):
                started = datetime.fromisoformat(str(current["started_at"]))
                current_view = {
                    "active": True,
                    "started_at": current.get("started_at"),
                    "duration_s": max((datetime.now(tz=started.tzinfo) - started).total_seconds(), 0.0),
                    "energy_wh": round(float(current.get("energy_wh", 0.0)), 3),
                    "samples": int(current.get("samples", 0)),
                    "max_power_w": float(current.get("max_power_w", 0.0)),
                    "origin": current.get("origin", "UNKNOWN"),
                }
            result[machine_id] = {
                "name": rec.get("name", machine_id),
                "total_cycles": int(rec.get("total_cycles", 0)),
                "retained_cycles": len(cycles) if isinstance(cycles, list) else 0,
                "current": current_view or {"active": False},
                "last_cycle": deepcopy(cycles[-1]) if cycles else None,
                "average_duration_s_10": (sum(durations) / len(durations)) if durations else None,
                "average_energy_wh_10": (sum(energies) / len(energies)) if energies else None,
            }
        return result

    @staticmethod
    def _num(value: Any, digits: int = 1) -> float | None:
        if not isinstance(value, (int, float)):
            return None
        return round(float(value), digits)
