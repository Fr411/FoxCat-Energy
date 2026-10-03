from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .registry import registry_diagnostics


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator._build_data()
    snap = data["snapshot"]
    return {
        "entry": {"title": entry.title, "data": dict(entry.data)},
        "settings": dict(coordinator.settings),
        "core": dict(coordinator.core_state),
        "pri": dict(coordinator.pri_state),
        "load_shed": dict(coordinator.load_shed_state),
        "snapshot": {
            "pv_w": snap.pv_w,
            "house_w": snap.house_w,
            "export_w": snap.export_w,
            "import_w": snap.import_w,
            "grid_net_w": snap.grid_net_w,
            "boiler_temp_c": snap.boiler_temp_c,
            "boiler_power_w": snap.boiler_power_w,
            "boiler_on": snap.boiler_on,
            "machine_active": snap.machine_active,
            "valid": snap.valid,
        },
        "solar": {
            "available": coordinator.solar_forecast.available,
            "start": coordinator.solar_forecast.start,
            "end": coordinator.solar_forecast.end,
            "confidence": coordinator.solar_forecast.confidence,
            "potential": coordinator.solar_forecast.potential,
            "trend": coordinator.solar_forecast.trend,
            "reason": coordinator.solar_forecast.reason,
        },
        "registry": registry_diagnostics(hass, entry, coordinator.config),
        "legacy_conflict": data["legacy_conflict"],
    }
