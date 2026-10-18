from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any


TOSHIBA_G3_MODELS: dict[str, dict[str, Any]] = {
    "RAS-2M10G3AVG-E2": {"heads": 2, "cooling_kw": 3.3, "heating_kw": 4.0, "seer": 8.3, "scop": 4.6, "cooling_class": "A+++", "heating_class": "A++", "noise_dba": 46, "weight_kg": 31},
    "RAS-2M14G3AVG-E2": {"heads": 2, "cooling_kw": 4.0, "heating_kw": 4.4, "seer": 8.7, "scop": 4.8, "cooling_class": "A+++", "heating_class": "A++", "noise_dba": 46, "weight_kg": 35},
    "RAS-2M18G3AVG-E2": {"heads": 2, "cooling_kw": 5.2, "heating_kw": 5.6, "seer": 7.2, "scop": 4.5, "cooling_class": "A++", "heating_class": "A+", "noise_dba": 48, "weight_kg": 43},
    "RAS-3M18G3AVG-E3": {"heads": 3, "cooling_kw": 5.2, "heating_kw": 5.6, "seer": 8.7, "scop": 4.7, "cooling_class": "A+++", "heating_class": "A++", "noise_dba": 47, "weight_kg": 44},
    "RAS-3M26G3AVG-E3": {"heads": 3, "cooling_kw": 7.5, "heating_kw": 8.7, "seer": 8.5, "scop": 4.6, "cooling_class": "A+++", "heating_class": "A++", "noise_dba": 48, "weight_kg": 72},
    "RAS-4M27G3AVG-E4": {"heads": 4, "cooling_kw": 8.0, "heating_kw": 9.0, "seer": 8.3, "scop": 4.5, "cooling_class": "A++", "heating_class": "A++", "noise_dba": 53, "weight_kg": 72},
    "RAS-5M34G3AVG-E5": {"heads": 5, "cooling_kw": 10.0, "heating_kw": 12.0, "seer": 7.2, "scop": 4.3, "cooling_class": "A++", "heating_class": "A+", "noise_dba": 47, "weight_kg": 78},
}

TOSHIBA_COMPRESSOR = {
    "type": "DC Twin-Rotary",
    "heating_min_c": -20,
    "cooling_max_c": 46,
}

HVAC_EQUIPMENT_TYPES = (
    "PAC Air-Air",
    "PAC Air-Eau",
    "PAC Eau-Eau",
    "Chaudière Mazout",
    "Chaudière Gaz standard",
    "Chaudière Gaz condensation",
)
INDOOR_SIZES = ("07", "10", "13", "16/18", "22/24")
INDOOR_RANGES = (
    "Haori",
    "Daiseikai 9",
    "Shorai+ / Shorai Edge",
    "Seiya",
    "Silverstone (J2FVG)",
    "Gainable ultra-plat (45 Pa)",
    "Cassette compacte S4 (600x600)",
)


def hvac_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    records = config.get("hvac_equipment", [])
    return [record for record in records if isinstance(record, dict) and record.get("id")]
    # ConfigEntry data remains the source of truth; malformed legacy records are ignored.


def _entity_state(get_state: Callable[[str | None], Any], entity_id: Any) -> tuple[float | None, str | None, str | None]:
    if not entity_id:
        return None, None, None
    state = get_state(str(entity_id))
    if state is None or str(getattr(state, "state", "")).lower() in {"unknown", "unavailable", "none", ""}:
        return None, None, None
    try:
        value = float(state.state)
    except (TypeError, ValueError, OverflowError):
        return None, str(state.state), None
    if not math.isfinite(value):
        return None, str(state.state), None
    unit = str(getattr(state, "attributes", {}).get("unit_of_measurement", "")).lower()
    return value, str(state.state), unit


def _power_w(
    unit: dict[str, Any],
    get_state: Callable[[str | None], Any],
    *,
    voltage_v: float,
    power_factor: float,
) -> float | None:
    watts, _, unit_name = _entity_state(get_state, unit.get("power_sensor"))
    if watts is not None:
        if unit_name in {"kw", "kilowatt", "kilowatts"}:
            watts *= 1000.0
        return max(watts, 0.0)
    amps, _, current_unit = _entity_state(get_state, unit.get("current_sensor"))
    if amps is None:
        return None
    if current_unit in {"ma", "milliampere", "milliamperes"}:
        amps /= 1000.0
    return max(amps, 0.0) * voltage_v * power_factor


def _active(unit: dict[str, Any], get_state: Callable[[str | None], Any]) -> bool | None:
    _, raw_state, _ = _entity_state(get_state, unit.get("state_sensor"))
    if raw_state is None:
        return None
    return raw_state.lower() not in {"off", "false", "0", "closed", "idle", "unavailable"}


def aggregate_equipment(
    record: dict[str, Any],
    get_state: Callable[[str | None], Any],
) -> dict[str, Any]:
    """Return read-only power/status views; outdoor meters are not double-counted."""
    voltage_v = max(float(record.get("voltage_v") or 230.0), 1.0)
    power_factor = min(max(float(record.get("power_factor") or 0.9), 0.1), 1.0)
    kind = str(record.get("equipment_type") or "")
    indoor = [dict(item) for item in record.get("indoor_units", []) if isinstance(item, dict)]
    outdoor = [dict(item) for item in record.get("outdoor_units", []) if isinstance(item, dict)]

    if kind != "PAC Air-Air":
        direct = _power_w(record, get_state, voltage_v=voltage_v, power_factor=power_factor)
        active = _active(record, get_state)
        estimated = False
        if direct is None and active:
            direct = max(float(record.get("nominal_power_w") or 0.0), 0.0)
            estimated = direct > 0
        if direct is None:
            direct = 0.0
        status = "on" if direct > 0 or active is True else "off" if active is False else "unknown"
        units = [{
            "id": str(record.get("id")),
            "name": str(record.get("name")),
            "kind": "equipment",
            "power_w": direct,
            "status": status,
            "estimated": estimated,
            "power_sensor": record.get("power_sensor"),
            "current_sensor": record.get("current_sensor"),
            "state_sensor": record.get("state_sensor"),
        }]
        return {
            "power_w": direct,
            "status": status,
            "estimated": estimated,
            "components": units,
            "compressor": None,
        }

    outside_by_id = {str(unit.get("id")): unit for unit in outdoor}
    zones_by_outside: dict[str, list[dict[str, Any]]] = {}
    for zone in indoor:
        zones_by_outside.setdefault(str(zone.get("outdoor_id") or ""), []).append(zone)

    components: list[dict[str, Any]] = []
    total = 0.0
    used_estimate = False
    unit_values: dict[str, dict[str, Any]] = {}
    for outside_id, outside in outside_by_id.items():
        zones = zones_by_outside.get(outside_id, [])
        zone_readings = [
            (_power_w(zone, get_state, voltage_v=voltage_v, power_factor=power_factor), _active(zone, get_state), zone)
            for zone in zones
        ]
        measured_zones = [item for item in zone_readings if item[0] is not None]
        outside_power = _power_w(outside, get_state, voltage_v=voltage_v, power_factor=power_factor)
        outside_active = _active(outside, get_state)
        unit_values[outside_id] = {
            "id": outside_id,
            "name": str(outside.get("name") or outside_id),
            "kind": "outdoor",
            "power_w": outside_power or 0.0,
            "status": "on" if outside_power and outside_power > 0 or outside_active is True else "off" if outside_active is False else "unknown",
            "estimated": False,
            "model": outside.get("model"),
            "specifications": outside.get("specifications"),
            "power_sensor": outside.get("power_sensor"),
            "current_sensor": outside.get("current_sensor"),
            "state_sensor": outside.get("state_sensor"),
        }
        if measured_zones:
            group_power = sum(float(item[0]) for item in measured_zones)
            missing_active_zones = [
                item for item in zone_readings if item[0] is None and item[1] is True
            ]
            active_groups = max(
                sum(
                    _active(candidate, get_state) is True
                    or any(
                        _active(zone, get_state) is True
                        for zone in zones_by_outside.get(str(candidate.get("id")), [])
                    )
                    for candidate in outdoor
                ),
                1,
            )
            nominal_group_w = max(float(record.get("nominal_power_w") or 0.0), 0.0) / active_groups
            missing_estimate = min(
                max(nominal_group_w - group_power, 0.0),
                nominal_group_w * len(missing_active_zones) / max(len(zones), 1),
            )
            group_power += missing_estimate
            total += group_power
            used_estimate = used_estimate or missing_estimate > 0
            for watts, active, zone in zone_readings:
                active_now = active if active is not None else watts > 0
                zone_watts = float(watts or 0.0)
                estimated_zone = watts is None and active is True and missing_active_zones and missing_estimate > 0
                if estimated_zone:
                    zone_watts = missing_estimate / len(missing_active_zones)
                unit_values[str(zone.get("id"))] = {
                    "id": str(zone.get("id")),
                    "name": str(zone.get("name") or zone.get("id")),
                    "kind": "indoor",
                    "power_w": zone_watts,
                    "status": "on" if active_now is True else "off" if active_now is False else "unknown",
                    "estimated": bool(estimated_zone),
                    "size": zone.get("size"),
                    "range": zone.get("range"),
                    "outdoor_id": outside_id,
                    "power_sensor": zone.get("power_sensor"),
                    "current_sensor": zone.get("current_sensor"),
                    "state_sensor": zone.get("state_sensor"),
                }
        elif outside_power is not None:
            group_power = outside_power
            total += group_power
            active_zone_count = sum(active is True for _, active, _ in zone_readings)
            for watts, active, zone in zone_readings:
                estimated_zone = active is True and active_zone_count > 0
                unit_values[str(zone.get("id"))] = {
                    "id": str(zone.get("id")),
                    "name": str(zone.get("name") or zone.get("id")),
                    "kind": "indoor",
                    "power_w": outside_power / active_zone_count if estimated_zone else 0.0,
                    "status": "on" if active is True else "off" if active is False else "unknown",
                    "estimated": estimated_zone,
                    "size": zone.get("size"),
                    "range": zone.get("range"),
                    "outdoor_id": outside_id,
                    "power_sensor": zone.get("power_sensor"),
                    "current_sensor": zone.get("current_sensor"),
                    "state_sensor": zone.get("state_sensor"),
                }
        else:
            active_zones = sum(active is True for _, active, _ in zone_readings)
            active_group = outside_active is True or active_zones > 0
            if active_group:
                active_groups = sum(
                    _active(candidate, get_state) is True
                    or any(_active(zone, get_state) is True for zone in zones_by_outside.get(str(candidate.get("id")), []))
                    for candidate in outdoor
                )
                active_groups = max(active_groups, 1)
                group_power = max(float(record.get("nominal_power_w") or 0.0), 0.0) / active_groups
                total += group_power
                used_estimate = group_power > 0
            else:
                group_power = 0.0
            if group_power > 0:
                unit_values[outside_id].update(
                    power_w=group_power,
                    status="on",
                    estimated=True,
                )
            for _, active, zone in zone_readings:
                unit_values[str(zone.get("id"))] = {
                    "id": str(zone.get("id")),
                    "name": str(zone.get("name") or zone.get("id")),
                    "kind": "indoor",
                    "power_w": group_power / active_zones if active is True and active_zones else 0.0,
                    "status": "on" if active is True else "off" if active is False else "unknown",
                    "estimated": active is True and group_power > 0,
                    "size": zone.get("size"),
                    "range": zone.get("range"),
                    "outdoor_id": outside_id,
                    "power_sensor": zone.get("power_sensor"),
                    "current_sensor": zone.get("current_sensor"),
                    "state_sensor": zone.get("state_sensor"),
                }

    if not outdoor:
        total = 0.0
    components = list(unit_values.values())
    status_values = [item["status"] for item in components]
    if total > 0:
        status = "on"
    elif status_values and all(value == "off" for value in status_values):
        status = "off"
    else:
        status = "unknown"
    return {
        "power_w": total,
        "status": status,
        "estimated": used_estimate,
        "components": components,
        "compressor": dict(TOSHIBA_COMPRESSOR) if any(
            str(unit.get("model")) in TOSHIBA_G3_MODELS for unit in outdoor
        ) else None,
    }
