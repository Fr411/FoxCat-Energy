from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .const import (
    CONF_DISHWASHER_CYCLE,
    CONF_DISHWASHER_OFF_1,
    CONF_DISHWASHER_OFF_2,
    CONF_DISHWASHER_ON_1,
    CONF_DISHWASHER_ON_2,
    CONF_DISHWASHER_SOCKET,
    CONF_DRYER_CYCLE,
    CONF_DRYER_OFF_1,
    CONF_DRYER_OFF_2,
    CONF_DRYER_ON_1,
    CONF_DRYER_ON_2,
    CONF_DRYER_SOCKET,
    CONF_MACHINES_V13,
    CONF_WASHER_CYCLE,
    CONF_WASHER_OFF_1,
    CONF_WASHER_OFF_2,
    CONF_WASHER_ON_1,
    CONF_WASHER_ON_2,
    CONF_WASHER_SOCKET,
)

DEFAULT_ON_1 = "21:30:00"
DEFAULT_OFF_1 = "07:00:00"
DEFAULT_ON_2 = "10:30:00"
DEFAULT_OFF_2 = "17:00:00"


@dataclass(slots=True)
class MachineDefinition:
    machine_id: str
    name: str
    switch_entity: str
    cycle_entity: str | None = None
    power_sensor: str | None = None
    current_sensor: str | None = None
    voltage_sensor: str | None = None
    automatic_default: bool = True
    sheddable: bool = True
    on_1: str = DEFAULT_ON_1
    off_1: str = DEFAULT_OFF_1
    on_2: str = DEFAULT_ON_2
    off_2: str = DEFAULT_OFF_2
    legacy_setting_key: str | None = None
    cycle_start_w: float = 10.0
    cycle_start_confirm_s: float = 20.0
    cycle_duration_minutes: float = 120.0
    cycle_margin_minutes: float = 45.0
    cycle_end_w: float = 5.0
    cycle_end_confirm_minutes: float = 10.0

    @property
    def setting_key(self) -> str:
        return self.legacy_setting_key or f"machine_{self.machine_id}_enabled"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.machine_id,
            "name": self.name,
            "switch": self.switch_entity,
            "cycle": self.cycle_entity or "",
            "power_sensor": self.power_sensor or "",
            "current_sensor": self.current_sensor or "",
            "voltage_sensor": self.voltage_sensor or "",
            "automatic": self.automatic_default,
            "sheddable": self.sheddable,
            "on_1": self.on_1,
            "off_1": self.off_1,
            "on_2": self.on_2,
            "off_2": self.off_2,
            "cycle_start_w": self.cycle_start_w,
            "cycle_start_confirm_s": self.cycle_start_confirm_s,
            "cycle_duration_minutes": self.cycle_duration_minutes,
            "cycle_margin_minutes": self.cycle_margin_minutes,
            "cycle_end_w": self.cycle_end_w,
            "cycle_end_confirm_minutes": self.cycle_end_confirm_minutes,
        }


def _str(value: Any, default: str = "") -> str:
    return str(value if value not in (None, "") else default)


def machine_from_dict(raw: dict[str, Any]) -> MachineDefinition | None:
    machine_id = _str(raw.get("id")).strip()
    name = _str(raw.get("name")).strip()
    switch = _str(raw.get("switch")).strip()
    if not machine_id or not name or not switch:
        return None
    legacy_setting_key = {
        "washer": "washer_enabled",
        "dryer": "dryer_enabled",
        "dishwasher": "dishwasher_enabled",
    }.get(machine_id)
    return MachineDefinition(
        machine_id=machine_id,
        name=name,
        switch_entity=switch,
        cycle_entity=_str(raw.get("cycle")).strip() or None,
        power_sensor=_str(raw.get("power_sensor")).strip() or None,
        current_sensor=_str(raw.get("current_sensor")).strip() or None,
        voltage_sensor=_str(raw.get("voltage_sensor")).strip() or None,
        automatic_default=bool(raw.get("automatic", True)),
        sheddable=bool(raw.get("sheddable", True)),
        legacy_setting_key=legacy_setting_key,
        cycle_start_w=float(raw.get("cycle_start_w",10.0)),
        cycle_start_confirm_s=float(raw.get("cycle_start_confirm_s",20.0)),
        cycle_duration_minutes=float(raw.get("cycle_duration_minutes",120.0)),
        cycle_margin_minutes=float(raw.get("cycle_margin_minutes",45.0)),
        cycle_end_w=float(raw.get("cycle_end_w",5.0)),
        cycle_end_confirm_minutes=float(raw.get("cycle_end_confirm_minutes",10.0)),
        on_1=_str(raw.get("on_1"), DEFAULT_ON_1),
        off_1=_str(raw.get("off_1"), DEFAULT_OFF_1),
        on_2=_str(raw.get("on_2"), DEFAULT_ON_2),
        off_2=_str(raw.get("off_2"), DEFAULT_OFF_2),
    )


def legacy_machine_definitions(config: dict[str, Any]) -> list[MachineDefinition]:
    specs = [
        (
            "washer", "Lave-linge", CONF_WASHER_SOCKET, CONF_WASHER_CYCLE,
            CONF_WASHER_ON_1, CONF_WASHER_OFF_1, CONF_WASHER_ON_2, CONF_WASHER_OFF_2,
            "washer_enabled",
        ),
        (
            "dryer", "Sèche-linge", CONF_DRYER_SOCKET, CONF_DRYER_CYCLE,
            CONF_DRYER_ON_1, CONF_DRYER_OFF_1, CONF_DRYER_ON_2, CONF_DRYER_OFF_2,
            "dryer_enabled",
        ),
        (
            "dishwasher", "Lave-vaisselle", CONF_DISHWASHER_SOCKET, CONF_DISHWASHER_CYCLE,
            CONF_DISHWASHER_ON_1, CONF_DISHWASHER_OFF_1, CONF_DISHWASHER_ON_2, CONF_DISHWASHER_OFF_2,
            "dishwasher_enabled",
        ),
    ]
    result: list[MachineDefinition] = []
    for machine_id, name, swk, cyk, on1, off1, on2, off2, setting_key in specs:
        switch = _str(config.get(swk)).strip()
        if not switch:
            continue
        result.append(MachineDefinition(
            machine_id=machine_id,
            name=name,
            switch_entity=switch,
            cycle_entity=_str(config.get(cyk)).strip() or None,
            on_1=_str(config.get(on1), DEFAULT_ON_1),
            off_1=_str(config.get(off1), DEFAULT_OFF_1),
            on_2=_str(config.get(on2), DEFAULT_ON_2),
            off_2=_str(config.get(off2), DEFAULT_OFF_2),
            legacy_setting_key=setting_key,
        ))
    return result


def machine_definitions(config: dict[str, Any]) -> list[MachineDefinition]:
    raw = config.get(CONF_MACHINES_V13)
    if isinstance(raw, list):
        parsed = [m for item in raw if isinstance(item, dict) if (m := machine_from_dict(item)) is not None]
        # Une liste présente, même vide, signifie que la migration V1.3 a été faite.
        return parsed
    return legacy_machine_definitions(config)


def records_for_options(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw = config.get(CONF_MACHINES_V13)
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    return [m.as_dict() for m in legacy_machine_definitions(config)]


def time_minutes(value: Any, default: str) -> int:
    raw = _str(value, default)
    try:
        parts = raw.split(":")
        return (int(parts[0]) % 24) * 60 + (int(parts[1]) % 60)
    except (ValueError, IndexError, TypeError):
        h, m = default.split(":")[:2]
        return int(h) * 60 + int(m)


def within_time_window(now_minute: int, start_minute: int, stop_minute: int) -> bool:
    if start_minute == stop_minute:
        return False
    if start_minute < stop_minute:
        return start_minute <= now_minute < stop_minute
    return now_minute >= start_minute or now_minute < stop_minute


def machine_allowed(machine: MachineDefinition, now: datetime) -> bool:
    minute = now.hour * 60 + now.minute
    return (
        within_time_window(minute, time_minutes(machine.on_1, DEFAULT_ON_1), time_minutes(machine.off_1, DEFAULT_OFF_1))
        or within_time_window(minute, time_minutes(machine.on_2, DEFAULT_ON_2), time_minutes(machine.off_2, DEFAULT_OFF_2))
    )


def schedule_boundaries(machines: list[MachineDefinition]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for machine in machines:
        for value, default in (
            (machine.on_1, DEFAULT_ON_1), (machine.off_1, DEFAULT_OFF_1),
            (machine.on_2, DEFAULT_ON_2), (machine.off_2, DEFAULT_OFF_2),
        ):
            minute = time_minutes(value, default)
            result.add((minute // 60, minute % 60))
    return result
