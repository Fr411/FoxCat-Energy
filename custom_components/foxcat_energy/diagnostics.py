from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN,VERSION
async def async_get_config_entry_diagnostics(hass:HomeAssistant,entry:ConfigEntry)->dict:
 c=hass.data[DOMAIN][entry.entry_id]; d=c._build_data(); e=d.get('economic',{}); return {'versions':{'engine':VERSION,'dashboard':d.get('versions',{}).get('dashboard','1.7.1')},'migration':d.get('migration',{}),'tariff':{'behavior':c.settings.get('mode'),'price_source':c.settings.get('price_source'),'structure':c.settings.get('tariff_structure'),'network_policy':c.settings.get('network_policy')},'price_analyzer':e.get('price_analyzer',{}),'planner':e.get('planner',{}),'decision':e.get('decision',{}),'boiler':d.get('boiler_thermal',{}),'cycles':d.get('machine_cycles',{}),'energy_bus':d.get('energy_bus',{}),'pri':d.get('pri',{}),'load_shed':d.get('load_shed',{}),'core':d.get('core',{}),'settings':dict(c.settings)}
