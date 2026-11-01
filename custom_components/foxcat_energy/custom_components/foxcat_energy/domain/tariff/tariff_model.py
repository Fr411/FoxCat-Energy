from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from ..pricing.economic_optimizer import PricePoint
from ...const import (
    DISTRIBUTION_PROFILE_BI,
    DISTRIBUTION_PROFILE_IMPACT,
    DISTRIBUTION_PROFILE_SIMPLE,
    DISTRIBUTION_PROFILES,
    DYNAMIC_STRUCT_IMPACT,
    NETWORK_POLICIES,
    NETWORK_POLICY_BILLED_EXPORT,
    NETWORK_POLICY_COMPENSATION,
    NETWORK_POLICY_NOT_VALUED,
    NETWORK_POLICY_ZERO_INJECTION,
    PRICE_SOURCES,
    PRICE_SOURCE_CONTRACT,
    PRICE_SOURCE_DYNAMIC,
    PRICE_SOURCE_INTEGRATION,
    PRICE_SOURCE_VARIABLE,
    TARIFF_STRUCTURES,
    TARIFF_STRUCTURE_IMPACT,
    TARIFF_STRUCTURE_SIMPLE,
    TARIFF_STRUCTURE_TOU,
)
from .tariff import (
    distribution_period as _canonical_distribution_period,
    impact_period as _canonical_impact_period,
    tariff_period as _canonical_tariff_period,
)
# Keep former public aliases for compatibility with existing imports.
NETWORK_POLICY_TARIFFED = NETWORK_POLICY_BILLED_EXPORT
NETWORK_POLICY_ZERO = NETWORK_POLICY_ZERO_INJECTION
IMPACT_ADDER_KEYS = {
    "ECO": "impact_eco_adder_eur_kwh",
    "MEDIUM": "impact_medium_adder_eur_kwh",
    "PIC": "impact_peak_adder_eur_kwh",
}
@dataclass(frozen=True,slots=True)
class TariffDimensions:
    price_source:str; structure:str; network_policy:str; distribution_profile:str
    # MÉTHODE : TariffDimensions.dynamic — Dynamic
    @property
    def dynamic(self): return self.price_source in {PRICE_SOURCE_DYNAMIC,PRICE_SOURCE_INTEGRATION}
# FONCTION : tariff_dimensions — Tariff dimensions
def tariff_dimensions(settings):
    source=settings.get('price_source',PRICE_SOURCE_VARIABLE)
    structure=settings.get('tariff_structure',TARIFF_STRUCTURE_TOU)
    if source in {PRICE_SOURCE_DYNAMIC,PRICE_SOURCE_INTEGRATION}:
        structure={
            'Simple':TARIFF_STRUCTURE_SIMPLE,
            'Bi-horaire':TARIFF_STRUCTURE_TOU,
            'Impact':TARIFF_STRUCTURE_IMPACT,
            'Impact (Capacitaire)':TARIFF_STRUCTURE_IMPACT,
        }.get(settings.get('dynamic_structure'),structure)
    profile = distribution_profile(settings)
    return TariffDimensions(source,structure,settings.get('network_policy',NETWORK_POLICY_COMPENSATION),profile)


def distribution_profile(settings):
    """Return the independent distribution profile, or infer legacy settings."""
    profile = settings.get("distribution_profile")
    if profile in DISTRIBUTION_PROFILES:
        return profile
    legacy_structures = {
        value
        for key in ("dynamic_structure", "tariff_structure")
        if isinstance((value := settings.get(key)), str)
    }
    if legacy_structures & {
        DISTRIBUTION_PROFILE_IMPACT,
        DYNAMIC_STRUCT_IMPACT,
        TARIFF_STRUCTURE_IMPACT,
    }:
        return DISTRIBUTION_PROFILE_IMPACT
    if legacy_structures & {
        DISTRIBUTION_PROFILE_BI,
        TARIFF_STRUCTURE_TOU,
        "Bi-horaire",
        "Bi-horaire (HP/HC)",
    }:
        return DISTRIBUTION_PROFILE_BI
    return DISTRIBUTION_PROFILE_SIMPLE
# FONCTION : tou_period — Tou period
def tou_period(at,settings):
    return _canonical_tariff_period(at, settings)
# FONCTION : impact_period — Impact period
def impact_period(at,settings):
    return _canonical_impact_period(at, settings)


def distribution_period(at, settings):
    return _canonical_distribution_period(at, settings)


# FONCTION : final_client_price — Final client price
def final_client_price(base,at,settings):
    p=float(base)
    if not settings.get('price_curve_is_final',True): p+=sum(float(settings.get(k,0)) for k in ('tariff_network_component_eur_kwh','tariff_tax_component_eur_kwh','tariff_contract_component_eur_kwh'))
    period = distribution_period(at, settings)
    if period in IMPACT_ADDER_KEYS:
        p += float(settings.get(IMPACT_ADDER_KEYS[period], 0))
    elif period in {"HP", "HC"}:
        p += float(settings.get(f"tariff_tou_{period.lower()}_adder_eur_kwh", 0))
    return p
# FONCTION : apply_final_price_components — Apply final price components
def apply_final_price_components(points:Iterable[PricePoint],settings): return [PricePoint(x.at,final_client_price(x.price,x.at,settings),x.source) for x in points]
