from __future__ import annotations
from typing import Any
from .const import *
MIGRATION_MODEL_VERSION="1.7.1"
def migrate_settings_v171(settings:dict[str,Any]):
 out=dict(settings); notes=[]; old=str(out.get("mode",MODE_ECO)); regime=str(out.get("tariff_regime",TARIFF_MONO))
 if old in {MODE_DYNAMIC,"Prix dynamique","Tarification dynamique"} or regime==TARIFF_DYNAMIC: out["price_source"]=PRICE_SOURCE_DYNAMIC; out.setdefault("tariff_structure",TARIFF_STRUCTURE_SIMPLE); notes.append("Ancien Dynamique migré vers source Day-Ahead.")
 elif old in {MODE_BIHORAIRE,"ECS solaire","Bihoraire","Bi-horaire","HP/HC"} or regime in {TARIFF_TOU,"Bi-horaire HP/HC"}: out["price_source"]=out.get("price_source",PRICE_SOURCE_VARIABLE); out["tariff_structure"]=TARIFF_STRUCTURE_TOU; notes.append("Ancien HP/HC conservé.")
 else: out.setdefault("price_source",PRICE_SOURCE_VARIABLE); out.setdefault("tariff_structure",TARIFF_STRUCTURE_SIMPLE if regime in {TARIFF_SIMPLE,TARIFF_MONO} else TARIFF_STRUCTURE_TOU)
 if old in {MODE_ZERO,"Réinjection refusée"}: out["network_policy"]=NETWORK_POLICY_ZERO_INJECTION
 elif old=="Réinjection autorisée" and "network_policy" not in out: out["network_policy"]=NETWORK_POLICY_BILLED_EXPORT
 else: out.setdefault("network_policy",NETWORK_POLICY_COMPENSATION)
 out["mode"]=MODE_MANUAL if old==MODE_MANUAL else MODE_ALIASES.get(old,MODE_ECO); out["configuration_model_version"]=MIGRATION_MODEL_VERSION; out["legacy_mode_v160"]=old; out["legacy_tariff_regime_v160"]=regime
 return out,notes
def compatibility_tariff_regime(settings):
 if settings.get("price_source")==PRICE_SOURCE_DYNAMIC:return TARIFF_DYNAMIC
 if settings.get("tariff_structure")==TARIFF_STRUCTURE_TOU:return TARIFF_BI
 return TARIFF_MONO
