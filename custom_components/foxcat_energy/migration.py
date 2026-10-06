from __future__ import annotations
from typing import Any
from .const import *
MIGRATION_MODEL_VERSION = "1.7.3"
MIGRATION_MODEL_VERSION_V171 = "1.7.1"
def migrate_settings_v171(settings:dict[str,Any]):
 out=dict(settings); notes=[]; old=str(out.get("mode",MODE_ECO)); regime=str(out.get("tariff_regime",TARIFF_TOU))
 if old in {MODE_DYNAMIC,"Prix dynamique","Tarification dynamique"} or regime==TARIFF_DYNAMIC: out["price_source"]=PRICE_SOURCE_DYNAMIC; out.setdefault("tariff_structure",TARIFF_STRUCTURE_SIMPLE); notes.append("Ancien Dynamique migré vers source Day-Ahead.")
 elif old in {MODE_BIHORAIRE,"ECS solaire","Bihoraire","Bi-horaire","HP/HC"} or regime==TARIFF_TOU: out["price_source"]=out.get("price_source",PRICE_SOURCE_VARIABLE); out["tariff_structure"]=TARIFF_STRUCTURE_TOU; notes.append("Ancien HP/HC conservé.")
 else: out.setdefault("price_source",PRICE_SOURCE_VARIABLE); out.setdefault("tariff_structure",TARIFF_STRUCTURE_SIMPLE if regime==TARIFF_SIMPLE else TARIFF_STRUCTURE_TOU)
 if old in {MODE_ZERO,"Réinjection refusée"}: out["network_policy"]=NETWORK_POLICY_ZERO_INJECTION
 elif old=="Réinjection autorisée" and "network_policy" not in out: out["network_policy"]=NETWORK_POLICY_BILLED_EXPORT
 else: out.setdefault("network_policy",NETWORK_POLICY_COMPENSATION)
 out["mode"]=MODE_MANUAL if old==MODE_MANUAL else MODE_ALIASES.get(old,MODE_ECO); out["configuration_model_version"]=MIGRATION_MODEL_VERSION_V171; out["legacy_mode_v160"]=old; out["legacy_tariff_regime_v160"]=regime
 return out,notes
def compatibility_tariff_regime(settings):
 if settings.get("price_source")==PRICE_SOURCE_DYNAMIC:return TARIFF_DYNAMIC
 if settings.get("tariff_structure")==TARIFF_STRUCTURE_TOU:return TARIFF_TOU
 return TARIFF_SIMPLE


def migrate_settings_v173(settings: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
 out, notes = migrate_settings_v171(settings)

 mode = str(out.get("mode", MODE_ECO))
 out["mode"] = MODE_ALIASES.get(mode, mode if mode in MODES else MODE_ECO)

 price_source = str(out.get("price_source", PRICE_SOURCE_VARIABLE))
 if price_source not in PRICE_SOURCES:
     price_aliases = {
         "Dynamique": PRICE_SOURCE_DYNAMIC,
         "Dynamic": PRICE_SOURCE_DYNAMIC,
         "Fixe": PRICE_SOURCE_CONTRACT,
         "Contractuelle": PRICE_SOURCE_CONTRACT,
         "Variable": PRICE_SOURCE_VARIABLE,
     }
     out["price_source"] = price_aliases.get(price_source, PRICE_SOURCE_VARIABLE)
     notes.append("Source de prix invalide normalisée vers une option prise en charge.")

 structure = str(out.get("tariff_structure", TARIFF_STRUCTURE_TOU))
 if structure not in TARIFF_STRUCTURES:
     structure_aliases = {
         "Bi-horaire HP/HC": TARIFF_STRUCTURE_TOU,
         "Bihoraire": TARIFF_STRUCTURE_TOU,
         "HP/HC": TARIFF_STRUCTURE_TOU,
     }
     out["tariff_structure"] = structure_aliases.get(structure, TARIFF_STRUCTURE_TOU)
     notes.append("Structure tarifaire invalide normalisée vers une option prise en charge.")

 network_policy = str(out.get("network_policy", NETWORK_POLICY_COMPENSATION))
 if network_policy not in NETWORK_POLICIES:
     network_aliases = {
         NETWORK_POLICY_LEGACY_BILLED_EXPORT: NETWORK_POLICY_BILLED_EXPORT,
         "Réinjection autorisée": NETWORK_POLICY_BILLED_EXPORT,
         "Réinjection refusée": NETWORK_POLICY_ZERO_INJECTION,
     }
     out["network_policy"] = network_aliases.get(network_policy, NETWORK_POLICY_COMPENSATION)
     notes.append("Politique réseau invalide normalisée vers une option prise en charge.")

 out["tariff_regime"] = compatibility_tariff_regime(out)
 for key in (
     "device_inverter_enabled",
     "device_meter_enabled",
     "device_boiler_enabled",
     "device_machines_enabled",
 ):
     out.setdefault(key, True)
 out["configuration_model_version"] = MIGRATION_MODEL_VERSION
 return out, notes
