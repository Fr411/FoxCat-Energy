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
    OFFICIAL_MENU_STEPS,
)
from .machines import records_for_options



def _entity(domain: str | list[str], device_class: str | None = None) -> selector.EntitySelector:
    cfg: dict[str, Any] = {"domain": domain}
    if device_class:
        cfg["device_class"] = device_class
    return selector.EntitySelector(selector.EntitySelectorConfig(**cfg))


def _required(key: str, default: str) -> vol.Required:
    return vol.Required(key, default=default)


def _optional(key: str, default: str | None = None) -> vol.Optional:
    return vol.Optional(key, default=default) if default is not None else vol.Optional(key)


def _normalise_value(value: Any) -> Any:
    """Return values that ConfigEntry storage can serialise reliably."""
    if isinstance(value, time):
        return value.isoformat()
    return value


def _normalise_input(user_input: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalise_value(value) for key, value in user_input.items()}


# IMPORTANT: schemas are built lazily.  Home Assistant first imports this module
# to register the ConfigFlow handler.  Building all selectors at import time made
# a single selector/API incompatibility capable of preventing the handler from
# being registered, which surfaced in the UI as "Invalid handler specified".
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


def _metronome_schema() -> vol.Schema:
    return vol.Schema(
        {
            _optional(CONF_METRONOME_FALLBACK_SENSOR): _entity("sensor"),
        }
    )


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



def _machine_record_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    current = current or {}
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


def _machine_choice_schema(records: list[dict[str, Any]]) -> vol.Schema:
    choices = {str(item.get("id")): str(item.get("name") or item.get("id")) for item in records if item.get("id")}
    return vol.Schema({vol.Required("machine_id"): vol.In(choices)})

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
        }
    )


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
}


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

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_boiler()
        return self.async_show_form(step_id="user", data_schema=_core_schema())

    async def async_step_boiler(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_pri()
        return self.async_show_form(step_id="boiler", data_schema=_boiler_schema())

    async def async_step_pri(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_machines()
        return self.async_show_form(step_id="pri", data_schema=_pri_schema())

    async def async_step_machines(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_pricing()
        return self.async_show_form(step_id="machines", data_schema=_machines_schema())

    async def async_step_pricing(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_hphc()
        return self.async_show_form(step_id="pricing", data_schema=_pricing_schema())

    async def async_step_hphc(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_ia()
        return self.async_show_form(step_id="hphc", data_schema=_hphc_schema())

    async def async_step_ia(self, user_input=None):
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            title = str(self._data.get(CONF_INSTALLATION_NAME, "FoxCat Energy"))
            await self.async_set_unique_id("foxcat_energy_main")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data=self._data)
        return self.async_show_form(step_id="ia", data_schema=_solar_schema())

    async def async_step_solar(self, user_input=None):
        """Compatibilité avec l'ancien nom de l'étape EMS 2 solaire."""
        return await self.async_step_ia(user_input)

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

    def __init__(self) -> None:
        super().__init__()
        self._pending_options: dict[str, Any] | None = None
        self._selected_machine_id: str | None = None

    def _ensure_pending(self) -> dict[str, Any]:
        if self._pending_options is None:
            self._pending_options = dict(self.config_entry.options)
        return self._pending_options

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

    async def async_step_init(self, user_input=None):
        self._ensure_pending()
        return self.async_show_menu(
            step_id="init",
            menu_options=list(OFFICIAL_MENU_STEPS),
        )

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
        return self.async_show_form(
            step_id=step_id,
            data_schema=_schema_with_current(schema, self._effective()),
        )

    async def async_step_sources(self, user_input=None):
        return await self._section("core", user_input)

    async def _info_section(self, step_id: str, user_input=None, return_step: str = "init"):
        if user_input is not None:
            return await getattr(self, f"async_step_{return_step}")()
        return self.async_show_form(step_id=step_id, data_schema=vol.Schema({}))

    async def async_step_energy(self, user_input=None):
        return await self._info_section("energy", user_input)

    async def async_step_inverter(self, user_input=None):
        return await self._section("pri", user_input)

    async def async_step_ems(self, user_input=None):
        return self.async_show_menu(
            step_id="ems",
            menu_options=["ems_core", "ia", "init"],
        )

    async def async_step_ems_core(self, user_input=None):
        return await self._info_section("ems_core", user_input, return_step="ems")

    async def async_step_ia(self, user_input=None):
        return await self._section("ia", user_input, return_step="ems")

    async def async_step_energy_bus(self, user_input=None):
        return await self._info_section("energy_bus", user_input)

    async def async_step_metronome(self, user_input=None):
        return await self._section("metronome", user_input)

    async def async_step_diagnostic(self, user_input=None):
        return await self._info_section("diagnostic", user_input)

    # Compatibility with the pre-1.6 route name.
    async def async_step_core(self, user_input=None):
        return await self._section("core", user_input)

    async def async_step_boiler(self, user_input=None):
        return await self._section("boiler", user_input)

    async def async_step_pri(self, user_input=None):
        return await self._section("pri", user_input)

    def _machine_records(self) -> list[dict[str, Any]]:
        effective = self._effective()
        return records_for_options(effective)

    def _store_machine_records(self, records: list[dict[str, Any]]) -> None:
        self._ensure_pending()[CONF_MACHINES_V13] = records

    async def async_step_machines(self, user_input=None):
        return self.async_show_menu(
            step_id="machines",
            menu_options=["machine_add", "machine_edit", "machine_remove", "machine_learning", "init"],
        )

    async def async_step_machine_add(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="machine_add", data_schema=_machine_record_schema())
        record = _normalise_input(user_input)
        record["id"] = uuid4().hex[:12]
        records = self._machine_records()
        records.append(record)
        self._store_machine_records(records)
        return await self.async_step_machines()

    async def async_step_machine_edit(self, user_input=None):
        records = self._machine_records()
        if not records:
            return self.async_abort(reason="no_machines_configured")
        if user_input is None:
            return self.async_show_form(step_id="machine_edit", data_schema=_machine_choice_schema(records))
        self._selected_machine_id = str(user_input["machine_id"])
        return await self.async_step_machine_edit_form()

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

    async def async_step_machine_remove(self, user_input=None):
        records = self._machine_records()
        if not records:
            return self.async_abort(reason="no_machines_configured")
        if user_input is None:
            return self.async_show_form(step_id="machine_remove", data_schema=_machine_choice_schema(records))
        machine_id = str(user_input["machine_id"])
        self._store_machine_records([item for item in records if str(item.get("id")) != machine_id])
        return await self.async_step_machines()

    async def async_step_machine_learning(self, user_input=None):
        return self.async_show_menu(
            step_id="machine_learning",
            menu_options=["machine_learning_info", "machines"],
        )

    async def async_step_machine_learning_info(self, user_input=None):
        return await self._info_section("machine_learning_info", user_input, return_step="machine_learning")

    async def async_step_pricing(self, user_input=None):
        return self.async_show_menu(
            step_id="pricing",
            menu_options=["pricing_dynamic", "hphc", "init"],
        )

    async def async_step_pricing_dynamic(self, user_input=None):
        return await self._section("pricing_dynamic", user_input, return_step="pricing")

    async def async_step_hphc(self, user_input=None):
        return await self._section("hphc", user_input, return_step="pricing")

    async def async_step_solar(self, user_input=None):
        """Compatibilité options avec l'ancien nom EMS 2 solaire."""
        return await self.async_step_ia(user_input)

    async def async_step_finish(self, user_input=None):
        return self.async_create_entry(title="", data=self._ensure_pending())
