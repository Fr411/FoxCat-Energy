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
    CONF_INSTALLATION_NAME,
    CONF_GRID_SIGNED_SENSOR,
    CONF_GRID_SIGN_CONVENTION,
    GRID_SIGN_IMPORT_POSITIVE,
    GRID_SIGN_EXPORT_POSITIVE,
    CONF_PV_SENSOR,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_TEMP_SENSOR,
    CONF_BOILER_POWER_SENSOR,
    CONF_BOILER_VOLUME,
    CONF_BOILER_ELEMENT_POWER,
    CONF_BOILER_COLD_WATER_TEMP,
    CONF_BOILER_BINARY,
    CONF_PRI_L1,
    CONF_PRI_L2,
    CONF_PRI_L3,
    CONF_PRI_L4,
    CONF_INVERTER_POWER_SENSOR,
    CONF_MACHINES_V13,
    DOMAIN,
)
from .machines import records_for_options
from .tariff_prices import CONF_TARIFF_MONO_PRICE_SENSOR, TARIFF_HPHC_BI, TARIFF_HPHC_MONO, TARIFF_DYNAMIQUE
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
)

def _entity(domain: str | list[str], device_class: str | None = None) -> selector.EntitySelector:
    cfg: dict[str, Any] = {"domain": domain}
    if device_class:
        cfg["device_class"] = device_class
    return selector.EntitySelector(selector.EntitySelectorConfig(**cfg))

def _normalise_value(value: Any) -> Any:
    if isinstance(value, time):
        return value.isoformat()
    return value

def _normalise_input(user_input: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalise_value(value) for key, value in user_input.items()}

class FoxCatEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Assistant de configuration guidé et professionnalisé pour FoxCat Energy."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Étape 0 : Choix du type de contrat d'électricité du client."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        
        return self.async_show_menu(
            step_id="user",
            menu_options=["menu_hphc", "menu_dynamique"],
        )

    async def async_step_menu_hphc(self, user_input: dict[str, Any] | None = None):
        """Sous-menu Tarifs Fixes ou Bihoraires (HP/HC)."""
        if user_input is not None:
            self._data["tariff_family"] = "hphc"
            self._data["tariff_structure"] = user_input["tariff_structure"]
            return await self.async_step_metering()
        
        return self.async_show_form(
            step_id="menu_hphc",
            data_schema=vol.Schema({
                vol.Required("tariff_structure", default=TARIFF_HPHC_MONO): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": TARIFF_HPHC_MONO, "label": "Tarif Monohoraire (Prix fixe unique 24h/24)"},
                            {"value": TARIFF_HPHC_BI, "label": "Tarif Bihoraire (Heures Pleines / Heures Creuses)"},
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            })
        )

    async def async_step_menu_dynamique(self, user_input: dict[str, Any] | None = None):
        """Sous-menu Tarification Dynamique (Heure par Heure / Spot)."""
        if user_input is not None:
            self._data["tariff_family"] = "dynamique"
            self._data["tariff_structure"] = "Dynamique"
            return await self.async_step_metering()
        
        return self.async_show_form(
            step_id="menu_dynamique",
            data_schema=vol.Schema({
                vol.Required("tariff_structure", default="Spot"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "Spot", "label": "Tarif Dynamique / Heure par Heure (EPEX Spot / Luminus Dynamic)"},
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            })
        )

    async def async_step_metering(self, user_input: dict[str, Any] | None = None):
        """Étape 1 : Comptage et Connexion au Réseau."""
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_inverter_battery()
        
        return self.async_show_form(
            step_id="metering",
            data_schema=vol.Schema({
                vol.Required(CONF_INSTALLATION_NAME, default="FoxCat Energy"): selector.TextSelector(),
                vol.Required("meter_type", default="numerique"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "analogique", "label": "Compteur Analogique (Pinces ampèremétriques type Shelly/Smappee)"},
                            {"value": "numerique", "label": "Compteur Numérique (Passerelle / Intégration cloud ou API)"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_GRID_SIGNED_SENSOR, default="sensor.consommation_instantanee_0"): _entity("sensor", "power"),
                vol.Required(CONF_GRID_SIGN_CONVENTION, default=GRID_SIGN_IMPORT_POSITIVE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": GRID_SIGN_IMPORT_POSITIVE, "label": "Positif = Prélèvement réseau / Négatif = Réinjection"},
                            {"value": GRID_SIGN_EXPORT_POSITIVE, "label": "Positif = Réinjection / Négatif = Prélèvement réseau"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_PV_SENSOR, default="sensor.homefoxcat_load_solaire"): _entity("sensor", "power"),
            })
        )

    async def async_step_inverter_battery(self, user_input: dict[str, Any] | None = None):
        """Étape 2 : Onduleur et Stockage Batterie."""
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_boiler()
        
        return self.async_show_form(
            step_id="inverter_battery",
            data_schema=vol.Schema({
                vol.Required("inverter_brand", default="SolarEdge"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["SolarEdge", "Enphase", "Huawei", "SMA", "Autre / Générique"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_INVERTER_POWER_SENSOR, default="sensor.onduleur_puissance_ac"): _entity("sensor", "power"),
                vol.Optional("has_battery", default=False): selector.BooleanSelector(),
                vol.Optional(CONF_BATTERY_CAPACITY, default=10.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=1000, step=0.1, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                ),
            })
        )

    async def async_step_boiler(self, user_input: dict[str, Any] | None = None):
        """Étape 3 : Chauffage et Ballon d'Eau Chaude (Boiler)."""
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_ev()
        
        return self.async_show_form(
            step_id="boiler",
            data_schema=vol.Schema({
                vol.Required(CONF_BOILER_CLIMATE, default="climate.buanderie_boiler_chauffe_eau"): _entity("climate"),
                vol.Required(CONF_BOILER_TEMP_SENSOR, default="sensor.boiler_sonde_temperature"): _entity("sensor", "temperature"),
                vol.Required(CONF_BOILER_POWER_SENSOR, default="sensor.boiler_puissance"): _entity("sensor", "power"),
                vol.Required(CONF_BOILER_BINARY, default="binary_sensor.boiler"): _entity("binary_sensor"),
                vol.Optional(CONF_BOILER_VOLUME, default=250.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=50, max=1000, step=10, unit_of_measurement="L", mode=selector.NumberSelectorMode.BOX)
                ),
            })
        )

    async def async_step_ev(self, user_input: dict[str, Any] | None = None):
        """Étape 4 : Recharge Véhicule Électrique (VE)."""
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            return await self.async_step_machines()
        
        return self.async_show_form(
            step_id="ev",
            data_schema=vol.Schema({
                vol.Optional("ev_enabled", default=False): selector.BooleanSelector(),
                vol.Optional(CONF_EV_CAPACITY, default=50.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=200, step=1, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional("ev_charger_power_sensor", default="sensor.borne_ve_puissance"): _entity("sensor", "power"),
            })
        )

    async def async_step_machines(self, user_input: dict[str, Any] | None = None):
        """Étape 5 : Appareils et Électroménager Pilotables."""
        if user_input is not None:
            self._data.update(_normalise_input(user_input))
            title = str(self._data.get(CONF_INSTALLATION_NAME, "FoxCat Energy"))
            await self.async_set_unique_id("foxcat_energy_main")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data=self._data)
        
        return self.async_show_form(
            step_id="machines",
            data_schema=vol.Schema({
                vol.Optional(CONF_PRI_L1, default="switch.l1_pri"): _entity("switch"),
                vol.Optional(CONF_PRI_L2, default="switch.l2_pri"): _entity("switch"),
            })
        )
