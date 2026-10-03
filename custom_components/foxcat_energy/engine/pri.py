from __future__ import annotations
import math
from .models import EnergySnapshot, PriDecision

INVERTER_POWER_W=4000.0
LEVEL_STEP_PCT=10
LEVEL_STEP_W=400.0

def clamp(v,lo,hi): return max(lo,min(hi,v))
def score(import_w,export_w,weight_import,weight_export):
    return max(import_w,0.0)*weight_import+max(export_w,0.0)*weight_export

def house_target_level(house_w,step_w,weight_import=1.0,weight_export=1.0):
    """Diagnostic seulement; ne commande pas la réduction puissance onduleur."""
    if step_w<=0:return 100,0.0,0.0
    h=max(float(house_w),0.0)
    t=0 if h<=0 else int(clamp(math.ceil(h/step_w)*10,0,100))
    return t,0.0,0.0

def inverter_limit_w(level_pct:int)->float:
    return INVERTER_POWER_W*clamp(float(level_pct),0.0,100.0)/100.0

def _pv_hits_ceiling(pv_w,current_level,margin_w,ratio_threshold):
    limit_w=inverter_limit_w(current_level)
    if limit_w<=0:return False,limit_w,0.0
    ratio=max(float(pv_w),0.0)/limit_w
    return (pv_w>=max(limit_w-margin_w,0.0) or ratio>=ratio_threshold),limit_w,ratio

def decide_zero(snapshot:EnergySnapshot,current_level:int,settings:dict[str,object])->PriDecision:
    """Réduction puissance onduleur: réinjection maître + contrôle PV/plafond."""
    export_limit=max(float(settings.get("pri_export_acceptable_w",150.0)),0.0)
    import_limit=max(float(settings.get("pri_import_acceptable_w",200.0)),0.0)
    margin=max(float(settings.get("pri_pv_compare_tolerance_w",200.0)),0.0)
    ratio_threshold=max(.5,min(1.0,float(settings.get("pri_ceiling_ratio",.92))))
    current_level=int(clamp(current_level,0,100))
    diag,_,_=house_target_level(snapshot.house_w,float(settings.get("pri_step_w",400.0)))
    hits,limit_w,ratio=_pv_hits_ceiling(snapshot.pv_w,current_level,margin,ratio_threshold)

    # Réinjection : on réduit d'un palier à chaque trame.
    if snapshot.export_w>export_limit:
        target=max(current_level-LEVEL_STEP_PCT,0)
        return PriDecision("descente" if target<current_level else "maintien",current_level,target,
            f"Réinjection {snapshot.export_w:.0f} W : réduction puissance onduleur {current_level}% -> {target}%. "
            f"PV={snapshot.pv_w:.0f} W / plafond={limit_w:.0f} W.",
            snapshot.export_w,0.0,diag)

    # Prélèvement : on ne libère que si le PV touche réellement son plafond.
    if snapshot.import_w>import_limit:
        if current_level<100 and hits:
            target=min(current_level+LEVEL_STEP_PCT,100)
            return PriDecision("remontee",current_level,target,
                f"Prélèvement {snapshot.import_w:.0f} W et PV proche du plafond "
                f"({snapshot.pv_w:.0f}/{limit_w:.0f} W = {ratio*100:.0f} %) : "
                f"libération puissance onduleur {current_level}% -> {target}%.",
                snapshot.import_w,0.0,diag)
        return PriDecision("maintien",current_level,current_level,
            f"Prélèvement {snapshot.import_w:.0f} W mais PV sous le plafond "
            f"({snapshot.pv_w:.0f}/{limit_w:.0f} W = {ratio*100:.0f} %) : "
            f"maximum solaire instantané atteint, maintien {current_level}%.",
            snapshot.import_w,0.0,diag)

    return PriDecision("maintien",current_level,current_level,
        f"Zone neutre : réinjection={snapshot.export_w:.0f} W, prélèvement={snapshot.import_w:.0f} W, maintien {current_level}%.",
        0.0,0.0,diag)

def decide_dynamic(snapshot:EnergySnapshot,current_level:int,settings:dict[str,object],injection_price:float|None,boiler_absorbing:bool)->PriDecision:
    """PRI dynamique basé sur la valeur SIGNÉE de l'export.

    ``injection_price`` est normalisé par FoxCat : positif = recette d'export,
    négatif = coût d'export. Depuis 1.6.158, une valeur positive libère
    toujours le PRI à 100 % : le kill-switch prédictif ne peut pas brider une
    production solaire dont la réinjection est rémunératrice.
    """
    current_level=int(clamp(current_level,0,100))
    if injection_price is not None and float(injection_price)>0.0:
        return PriDecision(
            "remontee" if current_level<100 else "maintien",
            current_level,100,
            f"Dynamique : export valorisé à {float(injection_price):.4f} €/kWh, PRI libéré à 100 %.",
            0.0,0.0,100,
        )
    return decide_zero(snapshot,current_level,settings)
