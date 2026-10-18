from __future__ import annotations

from datetime import time
from uuid import uuid4
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_TASK,
    CONF_BOILER_BINARY,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_POWER_SENSOR,
    CONF_BOILER_VOLUME,
    CONF_BOILER_ELEMENT_POWER,
    CONF_BOILER_COLD_WATER_TEMP,
    CONF_BOILER_RESISTANCE_TEMP_SENSOR,
    CONF_BOILER_TEMP_SENSOR,
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
    CONF_FORECAST_12H,
    CONF_FORECAST_1H,
    CONF_FORECAST_24H,
    CONF_FORECAST_NEXT_HOUR,
    CONF_FORECAST_NOW,
    CONF_FORECAST_PEAK_TODAY,
    CONF_FORECAST_PEAK_TOMORROW,
    CONF_FORECAST_REMAINING_TODAY,
    CONF_FORECAST_THIS_HOUR,
    CONF_FORECAST_TODAY,
    CONF_FORECAST_TOMORROW,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_GRID_LEGACY_SENSOR,
    CONF_GRID_SIGNED_SENSOR,
    CONF_GRID_SIGN_CONVENTION,
    GRID_SIGN_IMPORT_POSITIVE,
    GRID_SIGN_EXPORT_POSITIVE,
    CONF_METRONOME_SENSOR,
    CONF_METRONOME_FALLBACK_SENSOR,
    CONF_HOUSE_SENSOR,
    CONF_INSTALLATION_NAME,
    CONF_HVAC_EQUIPMENT,
    CONF_MACHINES_V13,
    CONF_PRICE_AVG_TODAY,
    CONF_PRICE_AVG_TOMORROW,
    CONF_PRICE_CURRENT,
    CONF_PRICE_INJECTION,
    CONF_PRICE_MAX_TODAY,
    CONF_PRICE_MAX_TOMORROW,
    CONF_PRICE_MIN_TODAY,
    CONF_PRICE_MIN_TOMORROW,
    CONF_PRICE_NEXT,
    CONF_PRICE_TOMORROW_AVAILABLE,
    CONF_PRICE_FORECAST_IMPORT,
    CONF_PRICE_FORECAST_EXPORT,
    CONF_DYNAMIC_EXPORT_SIGN_CONVENTION,
    DYNAMIC_EXPORT_NEGATIVE_IS_REVENUE,
    DYNAMIC_EXPORT_POSITIVE_IS_REVENUE,
    CONF_PRI_L1,
    CONF_PRI_L2,
    CONF_PRI_L3,
    CONF_PRI_L4,
    CONF_INVERTER_POWER_SENSOR,
    CONF_PV_SENSOR,
    CONF_TARIFF_HP_END_1,
    CONF_TARIFF_HP_END_2,
    CONF_TARIFF_HP_START_1,
    CONF_TARIFF_HP_START_2,
    CONF_TARIFF_FIXED_INJECTION_PRICE,
    CONF_TARIFF_HP_PRICE_SENSOR,
    CONF_TARIFF_HC_PRICE_SENSOR,
    CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR,
    CONF_WASHER_CYCLE,
    CONF_WASHER_OFF_1,
    CONF_WASHER_OFF_2,
    CONF_WASHER_ON_1,
    CONF_WASHER_ON_2,
    CONF_WASHER_SOCKET,
    DOMAIN,
    DEFAULT_DYNAMIC_HIGH_POSITION_PCT,
    OFFICIAL_MENU_STEPS,
)
from .machines import records_for_options
from .hvac import HVAC_EQUIPMENT_TYPES, INDOOR_RANGES, INDOOR_SIZES, TOSHIBA_G3_MODELS
from .tariff_prices import CONF_TARIFF_MONO_PRICE_SENSOR, active_tariff, TARIFF_HPHC_BI, TARIFF_HPHC_MONO, TARIFF_DYNAMIQUE
from .virtual_assets.config import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE,
    CONF_BATTERY_MAX_DISCHARGE,
    CONF_BATTERY_RESERVE,
    CONF_ENABLED as CONF_VIRTUAL_ASSETS_ENABLED,
    CONF_EV_CAPACITY,
    CONF_EV_CHARGE_EFFICIENCY,
    CONF_EV_ENABLED,
    CONF_EV_MAX_CHARGE,
    CONF_SHADOW as CONF_VIRTUAL_ASSETS_SHADOW,
)



# FONCTION : _entity — Entity
def _entity(domain: str | list[str], device_class: str | None = None) -> selector.EntitySelector:
    cfg: dict[str, Any] = {"domain": domain}
    if device_class:
        cfg["device_class"] = device_class
    return selector.EntitySelector(selector.EntitySelectorConfig(**cfg))


# FONCTION : _required — Required
def _required(key: str, default: str) -> vol.Required:
    return vol.Required(key, default=default)


# FONCTION : _optional — Optional
def _optional(key: str, default: str | None = None) -> vol.Optional:
    return vol.Optional(key, default=default) if default is not None else vol.Optional(key)


# FONCTION : _normalise_value — Return values that ConfigEntry storage can serialise reliably.
def _normalise_value(value: Any) -> Any:
    """Return values that ConfigEntry storage can serialise reliably."""
    if isinstance(value, time):
        return value.isoformat()
    return value


# FONCTION : _normalise_input — Normalise input
def _normalise_input(user_input: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalise_value(value) for key, value in user_input.items()}


# IMPORTANT: schemas are built lazily.  Home Assistant first imports this module
# to register the ConfigFlow handler.  Building all selectors at import time made
# a single selector/API incompatibility capable of preventing the handler from
# being registered, which surfaced in the UI as "Invalid handler specified".
# FONCTION : _grid_sign_selector — Grid sign selector
def _grid_sign_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": GRID_SIGN_IMPORT_POSITIVE, "label": "+ prélèvement / − réinjection"},
                {"value": GRID_SIGN_EXPORT_POSITIVE, "label": "+ réinjection / − prélèvement"},
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


HPHC_MONO = "Mono-horaire"
HPHC_BI = "Bi-horaire"
HPHC_STRUCTURES = [HPHC_MONO, HPHC_BI]
DYNAMIQUE_STRUCTURES = ["Simple", "Impact"]


# FONCTION : _structure_schema — Structure schema
def _structure_schema(options: list[str], default: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("tariff_structure", default=default): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options, mode=selector.SelectSelectorMode.LIST
                )
            )
        }
    )


# FONCTION : _core_schema — FoxCat 1.6 sources: only grid signed power + PV are mandatory.
def _core_schema() -> vol.Schema:
    """FoxCat 1.6 sources: only grid signed power + PV are mandatory."""
    return vol.Schema(
        {
            vol.Required(CONF_INSTALLATION_NAME, default="FoxCat Energy"): selector.TextSelector(),
            _required(CONF_GRID_SIGNED_SENSOR, "sensor.consommation_instantanee_0"): _entity("sensor"),
            vol.Required(CONF_GRID_SIGN_CONVENTION, default=GRID_SIGN_IMPORT_POSITIVE): _grid_sign_selector(),
            _required(CONF_PV_SENSOR, "sensor.homefoxcat_load_solaire"): _entity("sensor"),
            _optional(CONF_METRONOME_FALLBACK_SENSOR): _entity("sensor"),
        }
    )


# FONCTION : _metronome_schema — Metronome schema
def _metronome_schema() -> vol.Schema:
    return vol.Schema(
        {
            _optional(CONF_METRONOME_FALLBACK_SENSOR): _entity("sensor"),
        }
    )


# FONCTION : _boiler_schema — Boiler schema
def _boiler_schema() -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_BOILER_CLIMATE, "climate.buanderie_boiler_chauffe_eau"): _entity("climate"),
            _required(CONF_BOILER_TEMP_SENSOR, "sensor.garage_boiler_sonde_temperature_temperature"): _entity("sensor"),
            _optional(CONF_BOILER_RESISTANCE_TEMP_SENSOR): _entity("sensor"),
            _required(CONF_BOILER_POWER_SENSOR, "sensor.boiler_puissance"): _entity("sensor"),
            vol.Optional(CONF_BOILER_VOLUME, default=250.0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=20, max=2000, step=10, unit_of_measurement="L",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_BOILER_ELEMENT_POWER, default=1800.0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100, max=15000, step=50, unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_BOILER_COLD_WATER_TEMP, default=15.0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=35, step=0.5, unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            _required(CONF_BOILER_BINARY, "binary_sensor.boiler"): _entity("binary_sensor"),
        }
    )


# FONCTION : _pri_schema — Pri schema
def _pri_schema() -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_PRI_L1, "switch.l1_pri"): _entity("switch"),
            _required(CONF_PRI_L2, "switch.l2_pri"): _entity("switch"),
            _required(CONF_PRI_L3, "switch.l3_pri"): _entity("switch"),
            _required(CONF_PRI_L4, "switch.l4_pri"): _entity("switch"),
            _optional(CONF_INVERTER_POWER_SENSOR): _entity("sensor"),
        }
    )


# FONCTION : _machines_schema — Machines schema
def _machines_schema() -> vol.Schema:
    return vol.Schema(
        {
            _optional(CONF_WASHER_SOCKET, "switch.lave_linge_prise_1"): _entity("switch"),
            _optional(CONF_WASHER_CYCLE, "input_boolean.lave_linge_en_cours"): _entity(["binary_sensor", "input_boolean"]),
            vol.Optional(CONF_WASHER_ON_1, default="21:30:00"): selector.TimeSelector(),
            vol.Optional(CONF_WASHER_OFF_1, default="07:00:00"): selector.TimeSelector(),
            vol.Optional(CONF_WASHER_ON_2, default="10:30:00"): selector.TimeSelector(),
            vol.Optional(CONF_WASHER_OFF_2, default="17:00:00"): selector.TimeSelector(),
            _optional(CONF_DRYER_SOCKET, "switch.seche_linge_prise_1"): _entity("switch"),
            _optional(CONF_DRYER_CYCLE, "input_boolean.seche_linge_en_cours"): _entity(["binary_sensor", "input_boolean"]),
            vol.Optional(CONF_DRYER_ON_1, default="21:30:00"): selector.TimeSelector(),
            vol.Optional(CONF_DRYER_OFF_1, default="07:00:00"): selector.TimeSelector(),
            vol.Optional(CONF_DRYER_ON_2, default="10:30:00"): selector.TimeSelector(),
            vol.Optional(CONF_DRYER_OFF_2, default="17:00:00"): selector.TimeSelector(),
            _optional(CONF_DISHWASHER_SOCKET, "switch.lave_vaisselle_prise_1"): _entity("switch"),
            _optional(CONF_DISHWASHER_CYCLE, "input_boolean.lave_vaisselle_en_cours"): _entity(["binary_sensor", "input_boolean"]),
            vol.Optional(CONF_DISHWASHER_ON_1, default="21:30:00"): selector.TimeSelector(),
            vol.Optional(CONF_DISHWASHER_OFF_1, default="07:00:00"): selector.TimeSelector(),
            vol.Optional(CONF_DISHWASHER_ON_2, default="10:30:00"): selector.TimeSelector(),
            vol.Optional(CONF_DISHWASHER_OFF_2, default="17:00:00"): selector.TimeSelector(),
        }
    )



# FONCTION : _machine_record_schema — Machine record schema
def _machine_record_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    # FONCTION : opt_entity — Opt entity
    def opt_entity(key: str, domains: str | list[str]):
        value = str(current.get(key, "") or "")
        marker = vol.Optional(key, description={"suggested_value": value}) if value else vol.Optional(key)
        return marker, _entity(domains)

    cycle_marker, cycle_selector = opt_entity("cycle", ["binary_sensor", "input_boolean"])
    power_marker, power_selector = opt_entity("power_sensor", "sensor")
    current_marker, current_selector = opt_entity("current_sensor", "sensor")
    voltage_marker, voltage_selector = opt_entity("voltage_sensor", "sensor")
    return vol.Schema({
        vol.Required("name", default=str(current.get("name", ""))): selector.TextSelector(),
        vol.Required("switch", default=str(current.get("switch", ""))): _entity("switch"),
        cycle_marker: cycle_selector,
        power_marker: power_selector,
        current_marker: current_selector,
        voltage_marker: voltage_selector,
        vol.Optional("automatic", default=bool(current.get("automatic", True))): selector.BooleanSelector(),
        vol.Optional("sheddable", default=bool(current.get("sheddable", True))): selector.BooleanSelector(),
        vol.Optional("cycle_start_w", default=float(current.get("cycle_start_w", 10.0))): selector.NumberSelector(selector.NumberSelectorConfig(min=1,max=500,step=1,unit_of_measurement="W",mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("cycle_start_confirm_s", default=float(current.get("cycle_start_confirm_s", 20.0))): selector.NumberSelector(selector.NumberSelectorConfig(min=5,max=120,step=5,unit_of_measurement="s",mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("cycle_duration_minutes", default=float(current.get("cycle_duration_minutes", 120.0))): selector.NumberSelector(selector.NumberSelectorConfig(min=15,max=480,step=5,unit_of_measurement="min",mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("cycle_margin_minutes", default=float(current.get("cycle_margin_minutes", 45.0))): selector.NumberSelector(selector.NumberSelectorConfig(min=5,max=180,step=5,unit_of_measurement="min",mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("cycle_end_w", default=float(current.get("cycle_end_w", 5.0))): selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=100,step=1,unit_of_measurement="W",mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("cycle_end_confirm_minutes", default=float(current.get("cycle_end_confirm_minutes", 10.0))): selector.NumberSelector(selector.NumberSelectorConfig(min=1,max=60,step=1,unit_of_measurement="min",mode=selector.NumberSelectorMode.BOX)),
        vol.Optional("on_1", default=str(current.get("on_1", "21:30:00"))): selector.TimeSelector(),
        vol.Optional("off_1", default=str(current.get("off_1", "07:00:00"))): selector.TimeSelector(),
        vol.Optional("on_2", default=str(current.get("on_2", "10:30:00"))): selector.TimeSelector(),
        vol.Optional("off_2", default=str(current.get("off_2", "17:00:00"))): selector.TimeSelector(),
    })


# FONCTION : _machine_choice_schema — Machine choice schema
def _machine_choice_schema(records: list[dict[str, Any]]) -> vol.Schema:
    choices = {str(item.get("id")): str(item.get("name") or item.get("id")) for item in records if item.get("id")}
    return vol.Schema({vol.Required("machine_id"): vol.In(choices)})


def _hvac_record_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    fields: dict[Any, Any] = {
        vol.Required("name", default=str(current.get("name", ""))): selector.TextSelector(),
        vol.Required(
            "equipment_type",
            default=str(current.get("equipment_type", HVAC_EQUIPMENT_TYPES[0])),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=list(HVAC_EQUIPMENT_TYPES), mode=selector.SelectSelectorMode.DROPDOWN)
        ),
        vol.Required(
            "nominal_power_w",
            default=float(current.get("nominal_power_w", 2000.0)),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100000, step=100, unit_of_measurement="W", mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional("voltage_v", default=float(current.get("voltage_v", 230.0))): selector.NumberSelector(
            selector.NumberSelectorConfig(min=100, max=500, step=1, unit_of_measurement="V", mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional("power_factor", default=float(current.get("power_factor", 0.9))): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=1, step=0.01, mode=selector.NumberSelectorMode.BOX)
        ),
    }

    equipment_type = str(current.get("equipment_type", HVAC_EQUIPMENT_TYPES[0]))
    if equipment_type != "PAC Air-Air":
        for key, domain in (("power_sensor", "sensor"), ("current_sensor", "sensor"), ("state_sensor", ["binary_sensor", "climate", "input_boolean", "switch"])):
            fields[vol.Optional(key, description={"suggested_value": current.get(key, "")})] = _entity(domain)
        return vol.Schema(fields)

    model_options = [
        {"value": model, "label": model}
        for model in TOSHIBA_G3_MODELS
    ]
    for index in range(1, 6):
        outside = next(
            (item for item in current.get("outdoor_units", []) if item.get("id") == f"outdoor_{index}"),
            {},
        )
        model_key = f"outdoor_{index}_model"
        fields[vol.Optional(model_key, description={"suggested_value": outside.get("model", "")})] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=model_options, mode=selector.SelectSelectorMode.DROPDOWN)
        )
        for suffix, domain in (("power_sensor", "sensor"), ("current_sensor", "sensor"), ("state_sensor", ["binary_sensor", "climate", "input_boolean", "switch"])):
            key = f"outdoor_{index}_{suffix}"
            fields[vol.Optional(key, description={"suggested_value": outside.get(suffix, "")})] = _entity(domain)

    outside_choices = [
        {"value": f"outdoor_{index}", "label": f"Unité extérieure {index}"}
        for index in range(1, 6)
    ]
    for index in range(1, 6):
        zone = next(
            (item for item in current.get("indoor_units", []) if item.get("id") == f"indoor_{index}"),
            {},
        )
        for suffix in ("name", "size", "range", "outdoor_id", "power_sensor", "current_sensor", "state_sensor"):
            key = f"indoor_{index}_{suffix}"
            if suffix == "name":
                fields[vol.Optional(key, description={"suggested_value": zone.get(suffix, "")})] = selector.TextSelector()
            elif suffix == "size":
                fields[vol.Optional(key, description={"suggested_value": zone.get(suffix, "")})] = selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(INDOOR_SIZES), mode=selector.SelectSelectorMode.DROPDOWN)
                )
            elif suffix == "range":
                fields[vol.Optional(key, description={"suggested_value": zone.get(suffix, "")})] = selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(INDOOR_RANGES), mode=selector.SelectSelectorMode.DROPDOWN)
                )
            elif suffix == "outdoor_id":
                fields[vol.Optional(key, description={"suggested_value": zone.get(suffix, "")})] = selector.SelectSelector(
                    selector.SelectSelectorConfig(options=outside_choices, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            else:
                domain = ["binary_sensor", "climate", "input_boolean", "switch"] if suffix == "state_sensor" else "sensor"
                fields[vol.Optional(key, description={"suggested_value": zone.get(suffix, "")})] = _entity(domain)
    return vol.Schema(fields)


def _normalise_hvac_record(user_input: dict[str, Any], record_id: str) -> tuple[dict[str, Any] | None, bool]:
    equipment_type = str(user_input.get("equipment_type") or "")
    record: dict[str, Any] = {
        "id": record_id,
        "name": str(user_input.get("name") or "").strip(),
        "equipment_type": equipment_type,
        "nominal_power_w": max(float(user_input.get("nominal_power_w") or 0.0), 0.0),
        "voltage_v": max(float(user_input.get("voltage_v") or 230.0), 100.0),
        "power_factor": min(max(float(user_input.get("power_factor") or 0.9), 0.1), 1.0),
    }
    if not record["name"] or equipment_type not in HVAC_EQUIPMENT_TYPES:
        return None, False
    if equipment_type != "PAC Air-Air":
        record.update(
            power_sensor=str(user_input.get("power_sensor") or ""),
            current_sensor=str(user_input.get("current_sensor") or ""),
            state_sensor=str(user_input.get("state_sensor") or ""),
        )
        return record, True

    outdoor_units = []
    capacity = 0
    for index in range(1, 6):
        model = str(user_input.get(f"outdoor_{index}_model") or "")
        if not model:
            continue
        if model not in TOSHIBA_G3_MODELS:
            return None, False
        outside_id = f"outdoor_{index}"
        capacity += int(TOSHIBA_G3_MODELS[model]["heads"])
        outdoor_units.append({
            "id": outside_id,
            "name": f"Unité extérieure {index}",
            "model": model,
            "power_sensor": str(user_input.get(f"outdoor_{index}_power_sensor") or ""),
            "current_sensor": str(user_input.get(f"outdoor_{index}_current_sensor") or ""),
            "state_sensor": str(user_input.get(f"outdoor_{index}_state_sensor") or ""),
            "specifications": dict(TOSHIBA_G3_MODELS[model]),
        })
    if not outdoor_units:
        return None, False

    indoor_units = []
    for index in range(1, 6):
        outside_id = str(user_input.get(f"indoor_{index}_outdoor_id") or "")
        sensor_values = [
            user_input.get(f"indoor_{index}_{suffix}")
            for suffix in ("power_sensor", "current_sensor", "state_sensor")
        ]
        if not outside_id and not any(sensor_values):
            continue
        if outside_id not in {unit["id"] for unit in outdoor_units}:
            return None, False
        indoor_units.append({
            "id": f"indoor_{index}",
            "name": str(user_input.get(f"indoor_{index}_name") or f"Zone {index}"),
            "size": str(user_input.get(f"indoor_{index}_size") or ""),
            "range": str(user_input.get(f"indoor_{index}_range") or ""),
            "outdoor_id": outside_id,
            "power_sensor": str(user_input.get(f"indoor_{index}_power_sensor") or ""),
            "current_sensor": str(user_input.get(f"indoor_{index}_current_sensor") or ""),
            "state_sensor": str(user_input.get(f"indoor_{index}_state_sensor") or ""),
        })
    if len(indoor_units) > capacity:
        return None, False
    record["outdoor_units"] = outdoor_units
    record["indoor_units"] = indoor_units
    record["compressor"] = {"type": "DC Twin-Rotary", "heating_min_c": -20, "cooling_max_c": 46}
    return record, True


def _hvac_choice_schema(records: list[dict[str, Any]]) -> vol.Schema:
    choices = {str(item.get("id")): str(item.get("name") or item.get("id")) for item in records if item.get("id")}
    return vol.Schema({vol.Required("equipment_id"): vol.In(choices)})


# FONCTION : _dynamic_export_sign_selector — Dynamic export sign selector
def _dynamic_export_sign_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": DYNAMIC_EXPORT_POSITIVE_IS_REVENUE, "label": "Luminus Dynamic : positif = rémunération"},
                {"value": DYNAMIC_EXPORT_NEGATIVE_IS_REVENUE, "label": "Autre source : négatif = rémunération"},
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


# FONCTION : _pricing_schema — Pricing schema
def _pricing_schema() -> vol.Schema:
    return vol.Schema(
        {
            _optional(CONF_PRICE_CURRENT, "sensor.luminus_luminus_dynamic_wallonia_prix_actuel"): _entity("sensor"),
            _optional(CONF_PRICE_NEXT, "sensor.luminus_luminus_dynamic_wallonia_prix_heure_suivante"): _entity("sensor"),
            _optional(CONF_PRICE_INJECTION, "sensor.luminus_luminus_dynamic_wallonia_prix_d_injection"): _entity("sensor"),
            _optional(CONF_PRICE_MIN_TODAY, "sensor.luminus_luminus_dynamic_wallonia_minimum_aujourd_hui"): _entity("sensor"),
            _optional(CONF_PRICE_MAX_TODAY, "sensor.luminus_luminus_dynamic_wallonia_maximum_aujourd_hui"): _entity("sensor"),
            _optional(CONF_PRICE_AVG_TODAY, "sensor.luminus_luminus_dynamic_wallonia_moyenne_aujourd_hui"): _entity("sensor"),
            _optional(CONF_PRICE_MIN_TOMORROW, "sensor.luminus_luminus_dynamic_wallonia_minimum_demain"): _entity("sensor"),
            _optional(CONF_PRICE_MAX_TOMORROW, "sensor.luminus_luminus_dynamic_wallonia_maximum_demain"): _entity("sensor"),
            _optional(CONF_PRICE_AVG_TOMORROW, "sensor.luminus_luminus_dynamic_wallonia_moyenne_demain"): _entity("sensor"),
            _optional(CONF_PRICE_TOMORROW_AVAILABLE, "binary_sensor.luminus_luminus_dynamic_wallonia_prix_de_demain_disponibles"): _entity("binary_sensor"),
            _optional(CONF_PRICE_FORECAST_IMPORT): _entity("sensor"),
            _optional(CONF_PRICE_FORECAST_EXPORT): _entity("sensor"),
            vol.Required(CONF_DYNAMIC_EXPORT_SIGN_CONVENTION, default=DYNAMIC_EXPORT_POSITIVE_IS_REVENUE): _dynamic_export_sign_selector(),
            vol.Optional("dynamic_favorable_position_pct", default=30.0): selector.NumberSelector(selector.NumberSelectorConfig(min=5,max=60,step=1,unit_of_measurement="%",mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional("dynamic_high_position_pct", default=DEFAULT_DYNAMIC_HIGH_POSITION_PCT): selector.NumberSelector(selector.NumberSelectorConfig(min=60,max=95,step=1,unit_of_measurement="%",mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional("dynamic_favorable_max_hours", default=4.0): selector.NumberSelector(selector.NumberSelectorConfig(min=.25,max=12,step=.25,unit_of_measurement="h",mode=selector.NumberSelectorMode.SLIDER)),
            vol.Optional("dynamic_preferred_network_max_eur_kwh", default=.30): _price_number(.30,-1,2),
        }
    )


# FONCTION : _price_number — Price number
def _price_number(default: float, minimum: float = 0.0, maximum: float = 2.0) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=0.001,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="€/kWh",
        )
    )


# FONCTION : _hphc_schema — Fixed / dual-rate tariff values configured by the installer/user.
def _hphc_schema() -> vol.Schema:
    """Fixed / dual-rate tariff values configured by the installer/user."""
    return vol.Schema(
        {
            _optional(CONF_TARIFF_HP_PRICE_SENSOR, "sensor.luminus_luminus_comfyflex_wallonia_prix_heures_pleines_jour"): _entity("sensor"),
            _optional(CONF_TARIFF_HC_PRICE_SENSOR, "sensor.luminus_luminus_comfyflex_wallonia_prix_heures_creuses_nuit"): _entity("sensor"),
            _optional(CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR, "sensor.luminus_luminus_comfyflex_wallonia_prix_d_injection"): _entity("sensor"),
            vol.Optional(CONF_TARIFF_FIXED_INJECTION_PRICE, default=0.0): _price_number(0.0, -1.0, 2.0),
            vol.Optional(CONF_TARIFF_HP_START_1, default="07:00:00"): selector.TimeSelector(),
            vol.Optional(CONF_TARIFF_HP_END_1, default="11:00:00"): selector.TimeSelector(),
            vol.Optional(CONF_TARIFF_HP_START_2, default="17:00:00"): selector.TimeSelector(),
            vol.Optional(CONF_TARIFF_HP_END_2, default="22:00:00"): selector.TimeSelector(),
        }
    )


# FONCTION : _solar_schema — Solar schema
def _solar_schema() -> vol.Schema:
    return vol.Schema(
        {
            _optional(CONF_AI_TASK, "ai_task.google_ai_task"): _entity("ai_task"),
            _optional(CONF_FORECAST_NOW, "sensor.solar_production_forecast_production_d_electricite_estimee_maintenant"): _entity("sensor"),
            _optional(CONF_FORECAST_THIS_HOUR, "sensor.solar_production_forecast_production_d_energie_estimee_cette_heure"): _entity("sensor"),
            _optional(CONF_FORECAST_NEXT_HOUR, "sensor.solar_production_forecast_production_d_energie_estimee_heure_suivante"): _entity("sensor"),
            _optional(CONF_FORECAST_TODAY, "sensor.solar_production_forecast_production_d_energie_estimee_aujourd_hui"): _entity("sensor"),
            _optional(CONF_FORECAST_REMAINING_TODAY, "sensor.solar_production_forecast_production_d_energie_estimee_restante_aujourd_hui"): _entity("sensor"),
            _optional(CONF_FORECAST_1H, "sensor.solar_production_forecast_production_d_energie_estimee_en_1_heure"): _entity("sensor"),
            _optional(CONF_FORECAST_12H, "sensor.solar_production_forecast_production_d_energie_estimee_en_12_heures"): _entity("sensor"),
            _optional(CONF_FORECAST_24H, "sensor.solar_production_forecast_production_d_energie_estimee_en_24_heures"): _entity("sensor"),
            _optional(CONF_FORECAST_PEAK_TODAY, "sensor.solar_production_forecast_heure_de_pointe_de_puissance_la_plus_elevee_aujourd_hui"): _entity("sensor"),
            _optional(CONF_FORECAST_TOMORROW, "sensor.solar_production_forecast_estimation_de_la_production_d_energie_demain"): _entity("sensor"),
            _optional(CONF_FORECAST_PEAK_TOMORROW, "sensor.solar_production_forecast_heure_de_pointe_de_puissance_la_plus_elevee_demain"): _entity("sensor"),
        }
    )


def _virtual_assets_schema() -> vol.Schema:
    number = selector.NumberSelectorMode.BOX
    return vol.Schema(
        {
            vol.Optional(CONF_VIRTUAL_ASSETS_ENABLED, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_VIRTUAL_ASSETS_SHADOW, default=True): selector.BooleanSelector(),
            vol.Optional(CONF_BATTERY_CAPACITY, default=10.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=1000, step=0.1, unit_of_measurement="kWh", mode=number)
            ),
            vol.Optional(CONF_BATTERY_MAX_CHARGE, default=5.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=100, step=0.1, unit_of_measurement="kW", mode=number)
            ),
            vol.Optional(CONF_BATTERY_MAX_DISCHARGE, default=5.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=100, step=0.1, unit_of_measurement="kW", mode=number)
            ),
            vol.Optional(CONF_BATTERY_CHARGE_EFFICIENCY, default=95.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, step=1, unit_of_measurement="%", mode=number)
            ),
            vol.Optional(CONF_BATTERY_DISCHARGE_EFFICIENCY, default=95.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, step=1, unit_of_measurement="%", mode=number)
            ),
            vol.Optional(CONF_BATTERY_RESERVE, default=20.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%", mode=number)
            ),
            vol.Optional(CONF_EV_ENABLED, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_EV_CAPACITY, default=50.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=300, step=1, unit_of_measurement="kWh", mode=number)
            ),
            vol.Optional(CONF_EV_MAX_CHARGE, default=7.4): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=100, step=0.1, unit_of_measurement="kW", mode=number)
            ),
            vol.Optional(CONF_EV_CHARGE_EFFICIENCY, default=90.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, step=1, unit_of_measurement="%", mode=number)
            ),
        }
    )


_SCHEMA_BUILDERS = {
    "core": _core_schema,
    "metronome": _metronome_schema,
    "boiler": _boiler_schema,
    "inverter": _pri_schema,
    "pri": _pri_schema,
    "machines": _machines_schema,
    "pricing": _pricing_schema,
    "hphc": _hphc_schema,
    "solar": _solar_schema,
    "ia": _solar_schema,
    "pricing_dynamic": _pricing_schema,
    "battery_ev": _virtual_assets_schema,
}


# FONCTION : _schema_with_current — Schema with current
def _schema_with_current(schema: vol.Schema, current: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for marker, validator in schema.schema.items():
        key = marker.schema
        if key in current:
            value = _normalise_value(current[key])
            if isinstance(marker, vol.Required):
                new_marker = vol.Required(key, default=value)
            else:
                new_marker = vol.Optional(key, description={"suggested_value": value})
        else:
            new_marker = marker
        fields[new_marker] = validator
    return vol.Schema(fields)


class FoxCatEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial installation flow for FoxCat Energy."""

    VERSION = 1

    # MÉTHODE : FoxCatEnergyConfigFlow.__init__ — méthode spéciale __init__
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_user — Root menu: choose the contract family.
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Root menu: choose the contract family."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_show_menu(step_id="user", menu_options=["hphc", "dynamique"])

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_hphc — Branch A: HP/HC family, choose Mono-horaire or Bi-horaire.
    async def async_step_hphc(self, user_input: dict[str, Any] | None = None):
        """Branch A: HP/HC family, choose Mono-horaire or Bi-horaire."""
        if user_input is not None:
            self._data["tariff_family"] = "hphc"
            self._data["tariff_structure"] = user_input["tariff_structure"]
            if user_input["tariff_structure"] == HPHC_MONO:
                return await self.async_step_hphc_mono()
            return await self.async_step_hphc_bi()
        return self.async_show_form(
            step_id="hphc", data_schema=_structure_schema(HPHC_STRUCTURES, HPHC_MONO)
        )

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_hphc_mono — traitement asynchrone : step hphc mono
    async def async_step_hphc_mono(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_core()
        return self.async_show_form(
            step_id="hphc_mono",
            data_schema=vol.Schema({vol.Required(CONF_TARIFF_MONO_PRICE_SENSOR): _entity("sensor"), _optional(CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR): _entity("sensor")}),
        )

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_hphc_bi — traitement asynchrone : step hphc bi
    async def async_step_hphc_bi(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_core()
        return self.async_show_form(
            step_id="hphc_bi",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TARIFF_HP_PRICE_SENSOR): _entity("sensor"),
                    vol.Required(CONF_TARIFF_HC_PRICE_SENSOR): _entity("sensor"),
                    _optional(CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR): _entity("sensor"),
                }
            ),
        )

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_dynamique — Branch B: dynamic family, choose Simple, Bi-horaire or Dynamique.
    async def async_step_dynamique(self, user_input: dict[str, Any] | None = None):
        """Branch B: dynamic family, choose Simple, Bi-horaire or Dynamique."""
        if user_input is not None:
            self._data["tariff_family"] = "dynamique"
            self._data["tariff_structure"] = user_input["tariff_structure"]
            return await self.async_step_core()
        return self.async_show_form(
            step_id="dynamique",
            data_schema=_structure_schema(DYNAMIQUE_STRUCTURES, DYNAMIQUE_STRUCTURES[0]),
        )

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_core — traitement asynchrone : step core
    async def async_step_core(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_boiler()
        return self.async_show_form(step_id="core", data_schema=_core_schema())

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_boiler — traitement asynchrone : step boiler
    async def async_step_boiler(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_pri()
        return self.async_show_form(step_id="boiler", data_schema=_boiler_schema())

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_pri — traitement asynchrone : step pri
    async def async_step_pri(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_machines()
        return self.async_show_form(step_id="pri", data_schema=_pri_schema())

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_machines — traitement asynchrone : step machines
    async def async_step_machines(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            if self._data.get("tariff_family") == "dynamique":
                return await self.async_step_pricing()
            return await self.async_step_ia()
        return self.async_show_form(step_id="machines", data_schema=_machines_schema())

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_pricing — traitement asynchrone : step pricing
    async def async_step_pricing(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_ia()
        return self.async_show_form(step_id="pricing", data_schema=_pricing_schema())

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_ia — traitement asynchrone : step ia
    async def async_step_ia(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            title = str(self._data.get(CONF_INSTALLATION_NAME, "FoxCat Energy"))
            await self.async_set_unique_id("foxcat_energy_main")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data=self._data)
        return self.async_show_form(step_id="ia", data_schema=_solar_schema())

    # MÉTHODE : FoxCatEnergyConfigFlow.async_step_solar — Compatibilité avec l'ancien nom de l'étape EMS 2 solaire.
    async def async_step_solar(self, user_input=None):
        """Compatibilité avec l'ancien nom de l'étape EMS 2 solaire."""
        return await self.async_step_ia(user_input)

    # MÉTHODE : FoxCatEnergyConfigFlow.async_get_options_flow — Return the transactional options flow
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the transactional options flow.

        Home Assistant attaches config_entry to the OptionsFlow instance.
        """
        return FoxCatEnergyOptionsFlow()


class FoxCatEnergyOptionsFlow(config_entries.OptionsFlow):
    """Transactional options flow.

    No ConfigEntry mutation occurs while the menu is open.  Changes are kept in
    memory and committed once with async_create_entry() at "finish".  The
    ConfigEntry update listener can therefore reload FoxCat only after the flow
    is complete instead of destroying an active flow.
    """

    # MÉTHODE : FoxCatEnergyOptionsFlow.__init__ — méthode spéciale __init__
    def __init__(self) -> None:
        super().__init__()
        self._pending_options: dict[str, Any] | None = None
        self._selected_machine_id: str | None = None
        self._selected_hvac_id: str | None = None

    # MÉTHODE : FoxCatEnergyOptionsFlow._ensure_pending — Ensure pending
    def _ensure_pending(self) -> dict[str, Any]:
        if self._pending_options is None:
            self._pending_options = dict(self.config_entry.options)
        return self._pending_options

    # MÉTHODE : FoxCatEnergyOptionsFlow._effective — Effective
    def _effective(self) -> dict[str, Any]:
        data = dict(self.config_entry.data)
        data.update(self._ensure_pending())

        # V1.2.2 migration: V1.2.0/1.2.1 stored HP/HC prices in the
        # coordinator store because they were exposed only as number entities.
        # If the ConfigEntry does not contain them yet, pre-fill the new page
        # with the live values so existing user tuning is not lost.
        # Migration 1.5.x -> 1.6.0: l'ancien fallback pouvait être un capteur
        # d'export positif uniquement. Il ne doit pas être réutilisé par défaut
        # comme puissance réseau signée de secours.
        if CONF_GRID_SIGNED_SENSOR not in data:
            data[CONF_METRONOME_FALLBACK_SENSOR] = ""

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is not None:
            for key in (CONF_TARIFF_FIXED_INJECTION_PRICE,):
                if key not in data and key in coordinator.settings:
                    data[key] = coordinator.settings[key]
        return data

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_init — traitement asynchrone : step init
    async def async_step_init(self, user_input=None):
        self._ensure_pending()
        return self.async_show_menu(
            step_id="init",
            menu_options=list(OFFICIAL_MENU_STEPS),
        )

    # MÉTHODE : FoxCatEnergyOptionsFlow._section — Section
    async def _section(self, step_id: str, user_input, return_step: str = "init"):
        if user_input is not None:
            normalised = _normalise_input(user_input)
            pending = self._ensure_pending()
            pending.update(normalised)
            if step_id in {"core", "metronome"} and CONF_METRONOME_FALLBACK_SENSOR not in normalised:
                # Empty option explicitly shadows a pre-1.6 fallback stored in entry.data.
                pending[CONF_METRONOME_FALLBACK_SENSOR] = ""
            return await getattr(self, f"async_step_{return_step}")()
        schema = _SCHEMA_BUILDERS[step_id]()
        if step_id == "hphc" and active_tariff(self._effective()) == TARIFF_HPHC_MONO:
            hp_hc = (CONF_TARIFF_HP_PRICE_SENSOR, CONF_TARIFF_HC_PRICE_SENSOR)
            fields: dict[Any, Any] = {vol.Optional(CONF_TARIFF_MONO_PRICE_SENSOR): _entity("sensor")}
            fields.update({k: v for k, v in schema.schema.items() if k.schema not in hp_hc})
            schema = vol.Schema(fields)
        return self.async_show_form(
            step_id=step_id,
            data_schema=_schema_with_current(schema, self._effective()),
        )

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_sources — traitement asynchrone : step sources
    async def async_step_sources(self, user_input=None):
        return await self._section("core", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow._info_section — Info section
    async def _info_section(self, step_id: str, user_input=None, return_step: str = "init"):
        if user_input is not None:
            return await getattr(self, f"async_step_{return_step}")()
        return self.async_show_form(step_id=step_id, data_schema=vol.Schema({}))

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_energy — traitement asynchrone : step energy
    async def async_step_energy(self, user_input=None):
        return await self._info_section("energy", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_inverter — traitement asynchrone : step inverter
    async def async_step_inverter(self, user_input=None):
        return await self._section("pri", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_ems — traitement asynchrone : step ems
    async def async_step_ems(self, user_input=None):
        return self.async_show_menu(
            step_id="ems",
            menu_options=["ems_core", "ia", "init"],
        )

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_ems_core — traitement asynchrone : step ems core
    async def async_step_ems_core(self, user_input=None):
        return await self._info_section("ems_core", user_input, return_step="ems")

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_ia — traitement asynchrone : step ia
    async def async_step_ia(self, user_input=None):
        return await self._section("ia", user_input, return_step="ems")

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_energy_bus — traitement asynchrone : step energy bus
    async def async_step_energy_bus(self, user_input=None):
        return await self._info_section("energy_bus", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_metronome — traitement asynchrone : step metronome
    async def async_step_metronome(self, user_input=None):
        return await self._section("metronome", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_diagnostic — traitement asynchrone : step diagnostic
    async def async_step_diagnostic(self, user_input=None):
        return await self._info_section("diagnostic", user_input)

    # Compatibility with the pre-1.6 route name.
    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_core — traitement asynchrone : step core
    async def async_step_core(self, user_input=None):
        return await self._section("core", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_boiler — traitement asynchrone : step boiler
    async def async_step_boiler(self, user_input=None):
        return await self._section("boiler", user_input)

    def _hvac_records(self) -> list[dict[str, Any]]:
        records = self._effective().get(CONF_HVAC_EQUIPMENT, [])
        return [dict(item) for item in records if isinstance(item, dict) and item.get("id")]

    def _store_hvac_records(self, records: list[dict[str, Any]]) -> None:
        self._ensure_pending()[CONF_HVAC_EQUIPMENT] = records

    async def async_step_hvac(self, user_input=None):
        return self.async_show_menu(
            step_id="hvac",
            menu_options=["hvac_add", "hvac_edit", "hvac_remove", "init"],
        )

    async def async_step_hvac_add(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="hvac_add", data_schema=_hvac_record_schema())
        record, valid = _normalise_hvac_record(_normalise_input(user_input), uuid4().hex[:12])
        if not valid or record is None:
            return self.async_show_form(
                step_id="hvac_add",
                data_schema=_hvac_record_schema(),
                errors={"base": "invalid_hvac_config"},
            )
        records = self._hvac_records()
        records.append(record)
        self._store_hvac_records(records)
        return await self.async_step_hvac()

    async def async_step_hvac_edit(self, user_input=None):
        records = self._hvac_records()
        if not records:
            return self.async_abort(reason="no_hvac_configured")
        if user_input is None:
            return self.async_show_form(step_id="hvac_edit", data_schema=_hvac_choice_schema(records))
        self._selected_hvac_id = str(user_input["equipment_id"])
        return await self.async_step_hvac_edit_form()

    async def async_step_hvac_edit_form(self, user_input=None):
        records = self._hvac_records()
        current = next((item for item in records if str(item.get("id")) == self._selected_hvac_id), None)
        if current is None:
            return await self.async_step_hvac()
        if user_input is None:
            return self.async_show_form(
                step_id="hvac_edit_form",
                data_schema=_hvac_record_schema(current),
            )
        record, valid = _normalise_hvac_record(
            _normalise_input(user_input),
            self._selected_hvac_id or "",
        )
        if not valid or record is None:
            return self.async_show_form(
                step_id="hvac_edit_form",
                data_schema=_hvac_record_schema(current),
                errors={"base": "invalid_hvac_config"},
            )
        self._store_hvac_records([
            record if str(item.get("id")) == self._selected_hvac_id else item
            for item in records
        ])
        self._selected_hvac_id = None
        return await self.async_step_hvac()

    async def async_step_hvac_remove(self, user_input=None):
        records = self._hvac_records()
        if not records:
            return self.async_abort(reason="no_hvac_configured")
        if user_input is None:
            return self.async_show_form(step_id="hvac_remove", data_schema=_hvac_choice_schema(records))
        equipment_id = str(user_input["equipment_id"])
        self._store_hvac_records([item for item in records if str(item.get("id")) != equipment_id])
        return await self.async_step_hvac()

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_battery_ev — Configuration batterie et VE virtuels
    async def async_step_battery_ev(self, user_input=None):
        return await self._section("battery_ev", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_pri — traitement asynchrone : step pri
    async def async_step_pri(self, user_input=None):
        return await self._section("pri", user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow._machine_records — Machine records
    def _machine_records(self) -> list[dict[str, Any]]:
        effective = self._effective()
        return records_for_options(effective)

    # MÉTHODE : FoxCatEnergyOptionsFlow._store_machine_records — Store machine records
    def _store_machine_records(self, records: list[dict[str, Any]]) -> None:
        self._ensure_pending()[CONF_MACHINES_V13] = records

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machines — traitement asynchrone : step machines
    async def async_step_machines(self, user_input=None):
        return self.async_show_menu(
            step_id="machines",
            menu_options=["machine_add", "machine_edit", "machine_remove", "machine_learning", "init"],
        )

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machine_add — traitement asynchrone : step machine add
    async def async_step_machine_add(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="machine_add", data_schema=_machine_record_schema())
        record = _normalise_input(user_input)
        record["id"] = uuid4().hex[:12]
        records = self._machine_records()
        records.append(record)
        self._store_machine_records(records)
        return await self.async_step_machines()

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machine_edit — traitement asynchrone : step machine edit
    async def async_step_machine_edit(self, user_input=None):
        records = self._machine_records()
        if not records:
            return self.async_abort(reason="no_machines_configured")
        if user_input is None:
            return self.async_show_form(step_id="machine_edit", data_schema=_machine_choice_schema(records))
        self._selected_machine_id = str(user_input["machine_id"])
        return await self.async_step_machine_edit_form()

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machine_edit_form — traitement asynchrone : step machine edit form
    async def async_step_machine_edit_form(self, user_input=None):
        records = self._machine_records()
        current = next((item for item in records if str(item.get("id")) == self._selected_machine_id), None)
        if current is None:
            return await self.async_step_machines()
        if user_input is None:
            return self.async_show_form(step_id="machine_edit_form", data_schema=_machine_record_schema(current))
        updated = _normalise_input(user_input)
        updated["id"] = self._selected_machine_id
        records = [updated if str(item.get("id")) == self._selected_machine_id else item for item in records]
        self._store_machine_records(records)
        self._selected_machine_id = None
        return await self.async_step_machines()

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machine_remove — traitement asynchrone : step machine remove
    async def async_step_machine_remove(self, user_input=None):
        records = self._machine_records()
        if not records:
            return self.async_abort(reason="no_machines_configured")
        if user_input is None:
            return self.async_show_form(step_id="machine_remove", data_schema=_machine_choice_schema(records))
        machine_id = str(user_input["machine_id"])
        self._store_machine_records([item for item in records if str(item.get("id")) != machine_id])
        return await self.async_step_machines()

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machine_learning — traitement asynchrone : step machine learning
    async def async_step_machine_learning(self, user_input=None):
        return self.async_show_menu(
            step_id="machine_learning",
            menu_options=["machine_learning_info", "machines"],
        )

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_machine_learning_info — traitement asynchrone : step machine learning info
    async def async_step_machine_learning_info(self, user_input=None):
        return await self._info_section("machine_learning_info", user_input, return_step="machine_learning")

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_pricing — traitement asynchrone : step pricing
    async def async_step_pricing(self, user_input=None):
        options = ["pricing_dynamic", "hphc", "init"]
        return self.async_show_menu(step_id="pricing", menu_options=options)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_pricing_dynamic — traitement asynchrone : step pricing dynamic
    async def async_step_pricing_dynamic(self, user_input=None):
        return await self._section("pricing_dynamic", user_input, return_step="pricing")

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_hphc — traitement asynchrone : step hphc
    async def async_step_hphc(self, user_input=None):
        return await self._section("hphc", user_input, return_step="pricing")

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_solar — Compatibilité options avec l'ancien nom EMS 2 solaire.
    async def async_step_solar(self, user_input=None):
        """Compatibilité options avec l'ancien nom EMS 2 solaire."""
        return await self.async_step_ia(user_input)

    # MÉTHODE : FoxCatEnergyOptionsFlow.async_step_finish — traitement asynchrone : step finish
    async def async_step_finish(self, user_input=None):
        return self.async_create_entry(title="", data=self._ensure_pending())
