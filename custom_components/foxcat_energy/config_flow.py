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
    CONF_BOILER_BINARY,
    CONF_PRI_L1,
    CONF_PRI_L2,
    CONF_INVERTER_POWER_SENSOR,
    CONF_MACHINES_V13,
    DOMAIN,
)
from .machines import records_for_options
from .tariff_prices import CONF_TARIFF_MONO_PRICE_SENSOR, TARIFF_HPHC_BI, TARIFF_HPHC_MONO
from .virtual_assets.config import (
    CONF_BATTERY_CAPACITY,
    CONF_EV_CAPACITY,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return FoxCatEnergyOptionsFlow()


class FoxCatEnergyOptionsFlow(config_entries.OptionsFlow):
    """Menu de reconfiguration et d'options pour modifier les entités à tout moment."""

    def __init__(self) -> None:
        super().__init__()
        self._pending_options: dict[str, Any] | None = None

    def _ensure_pending(self) -> dict[str, Any]:
        if self._pending_options is None:
            self._pending_options = dict(self.config_entry.options)
            if not self._pending_options:
                self._pending_options = dict(self.config_entry.data)
        return self._pending_options

    async def async_step_init(self, user_input=None):
        """Menu principal des options : choix de la section à modifier."""
        self._ensure_pending()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "edit_metering",
                "edit_inverter_battery",
                "edit_boiler",
                "edit_ev",
                "edit_finish",
            ],
        )

    async def edit_section(self, step_id: str, schema: vol.Schema, user_input=None):
        """Fonction générique pour enregistrer ou afficher le formulaire d'une section."""
        if user_input is not None:
            pending = self._ensure_pending()
            pending.update(_normalise_input(user_input))
            return await self.async_step_init()
        
        current = self._ensure_pending()
        return self.async_show_form(
            step_id=step_id,
            data_schema=_schema_with_current(schema, current),
        )

    async def async_step_edit_metering(self, user_input=None):
        """Reconfigurer le comptage et le réseau."""
        schema = vol.Schema({
            vol.Required(CONF_GRID_SIGNED_SENSOR): _entity("sensor", "power"),
            vol.Required(CONF_PV_SENSOR): _entity("sensor", "power"),
        })
        return await self.edit_section("edit_metering", schema, user_input)

    async def async_step_edit_boiler(self, user_input=None):
        """Reconfigurer le boiler."""
        schema = vol.Schema({
            vol.Required(CONF_BOILER_CLIMATE): _entity("climate"),
            vol.Required(CONF_BOILER_TEMP_SENSOR): _entity("sensor", "temperature"),
            vol.Required(CONF_BOILER_POWER_SENSOR): _entity("sensor", "power"),
        })
        return await self.edit_section("edit_boiler", schema, user_input)

    async def async_step_edit_ev(self, user_input=None):
        """Reconfigurer le véhicule électrique."""
        schema = vol.Schema({
            vol.Optional("ev_enabled"): selector.BooleanSelector(),
            vol.Optional(CONF_EV_CAPACITY): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=200, step=1, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
            ),
        })
        return await self.edit_section("edit_ev", schema, user_input)

    async def async_step_edit_inverter_battery(self, user_input=None):
        """Reconfigurer l'onduleur et la batterie."""
        schema = vol.Schema({
            vol.Required(CONF_INVERTER_POWER_SENSOR): _entity("sensor", "power"),
            vol.Optional(CONF_BATTERY_CAPACITY): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=1000, step=0.1, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
            ),
        })
        return await self.edit_section("edit_inverter_battery", schema, user_input)

    async def async_step_edit_finish(self, user_input=None):
        """Sauvegarde finale de toutes les modifications."""
        return self.async_create_entry(title="", data=self._ensure_pending())
