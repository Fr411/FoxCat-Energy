from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from .economic_optimizer import PricePoint
PRICE_SOURCE_CONTRACT='Contractuelle / fixe'; PRICE_SOURCE_VARIABLE='Variable via entités Home Assistant'; PRICE_SOURCE_INTEGRATION='Intégration externe'; PRICE_SOURCE_DYNAMIC='Dynamique Day-Ahead'
PRICE_SOURCES=[PRICE_SOURCE_CONTRACT,PRICE_SOURCE_VARIABLE,PRICE_SOURCE_INTEGRATION,PRICE_SOURCE_DYNAMIC]
TARIFF_STRUCTURE_SIMPLE='Simple'; TARIFF_STRUCTURE_TOU='Bi-horaire'; TARIFF_STRUCTURE_IMPACT='Impact'; TARIFF_STRUCTURES=[TARIFF_STRUCTURE_SIMPLE,TARIFF_STRUCTURE_TOU,TARIFF_STRUCTURE_IMPACT]
NETWORK_POLICY_COMPENSATION='Compensation'; NETWORK_POLICY_TARIFFED='Injection tarifée'; NETWORK_POLICY_NOT_VALUED='Injection non valorisée'; NETWORK_POLICY_ZERO='Zéro injection'; NETWORK_POLICIES=[NETWORK_POLICY_COMPENSATION,NETWORK_POLICY_TARIFFED,NETWORK_POLICY_NOT_VALUED,NETWORK_POLICY_ZERO]
@dataclass(frozen=True,slots=True)
class TariffDimensions:
    price_source:str; structure:str; network_policy:str
    @property
    def dynamic(self): return self.price_source in {PRICE_SOURCE_DYNAMIC,PRICE_SOURCE_INTEGRATION}
def tariff_dimensions(settings):
    source=settings.get('price_source',PRICE_SOURCE_VARIABLE)
    structure=settings.get('tariff_structure',TARIFF_STRUCTURE_TOU)
    if source in {PRICE_SOURCE_DYNAMIC,PRICE_SOURCE_INTEGRATION}:
        structure={
            'Simple':TARIFF_STRUCTURE_SIMPLE,
            'Bi-horaire':TARIFF_STRUCTURE_TOU,
            'Impact (Capacitaire)':TARIFF_STRUCTURE_IMPACT,
        }.get(settings.get('dynamic_structure'),structure)
    return TariffDimensions(source,structure,settings.get('network_policy',NETWORK_POLICY_COMPENSATION))
def _minute(v,d):
    try: h,m=str(v or d).split(':')[:2]; return int(h)*60+int(m)
    except Exception: h,m=d.split(':'); return int(h)*60+int(m)
def _within(x,a,b): return a<=x<b if a<b else x>=a or x<b
def tou_period(at,settings):
    x=at.hour*60+at.minute
    ranges=[(_minute(settings.get('tariff_hp_start_1'),'07:00'),_minute(settings.get('tariff_hp_end_1'),'11:00')) ,(_minute(settings.get('tariff_hp_start_2'),'17:00'),_minute(settings.get('tariff_hp_end_2'),'22:00'))]
    return 'HP' if any(_within(x,a,b) for a,b in ranges) else 'HC'
def impact_period(at,settings):
    x=at.hour*60+at.minute
    if _within(x,_minute(settings.get('impact_peak_start'),'17:00'),_minute(settings.get('impact_peak_end'),'22:00')): return 'PIC'
    if _within(x,_minute(settings.get('impact_eco_start_1'),'01:00'),_minute(settings.get('impact_eco_end_1'),'07:00')) or _within(x,_minute(settings.get('impact_eco_start_2'),'11:00'),_minute(settings.get('impact_eco_end_2'),'17:00')): return 'ECO'
    return 'MEDIUM'
def final_client_price(base,at,settings):
    p=float(base)
    if not settings.get('price_curve_is_final',True): p+=sum(float(settings.get(k,0)) for k in ('tariff_network_component_eur_kwh','tariff_tax_component_eur_kwh','tariff_contract_component_eur_kwh'))
    dims=tariff_dimensions(settings)
    structure=dims.structure
    if structure==TARIFF_STRUCTURE_IMPACT: p+=float(settings.get({'ECO':'impact_eco_adder_eur_kwh','MEDIUM':'impact_medium_adder_eur_kwh','PIC':'impact_peak_adder_eur_kwh'}[impact_period(at,settings)],0))
    elif structure==TARIFF_STRUCTURE_TOU and dims.dynamic: p+=float(settings.get('tariff_tou_hp_adder_eur_kwh' if tou_period(at,settings)=='HP' else 'tariff_tou_hc_adder_eur_kwh',0))
    return p
def apply_final_price_components(points:Iterable[PricePoint],settings): return [PricePoint(x.at,final_client_price(x.price,x.at,settings),x.source) for x in points]
