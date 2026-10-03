
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from typing import Any

ZERO = {
    "house_kwh": 0.0, "pv_kwh": 0.0, "self_consumed_kwh": 0.0,
    "export_kwh": 0.0, "import_kwh": 0.0,
    "import_cost_eur": 0.0,
    # Compatibilité : export_value_eur reste le revenu brut de réinjection.
    "export_value_eur": 0.0,
    "export_revenue_eur": 0.0,
    "export_cost_eur": 0.0,
    "solar_avoided_cost_eur": 0.0,
}

def _bucket() -> dict[str, Any]:
    return {**ZERO, "appliances": {}}

class EnergyAccounting:
    """Comptabilité énergétique FoxCat, indépendante du moteur de décision EMS."""

    def __init__(self) -> None:
        self.day_key = ""
        self.month_key = ""
        self.year_key = ""
        self.today = _bucket()
        self.month = _bucket()
        self.year = _bucket()
        self.lifetime = _bucket()
        self.last_valid_ts: datetime | None = None
        self.last_save_ts: datetime | None = None

    def restore(self, raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        self.day_key = str(raw.get("day_key",""))
        self.month_key = str(raw.get("month_key",""))
        self.year_key = str(raw.get("year_key",""))
        for name in ("today","month","year","lifetime"):
            val=raw.get(name)
            if isinstance(val,dict):
                setattr(self,name,val)
        self.last_valid_ts = None  # never integrate downtime after HA restart

    def dump(self) -> dict[str, Any]:
        return {
            "day_key": self.day_key, "month_key": self.month_key, "year_key": self.year_key,
            "today": self.today, "month": self.month, "year": self.year, "lifetime": self.lifetime,
        }

    def _rollover(self, now: datetime) -> None:
        d,m,y=now.strftime("%Y-%m-%d"),now.strftime("%Y-%m"),now.strftime("%Y")
        if self.day_key and self.day_key != d: self.today=_bucket()
        if self.month_key and self.month_key != m: self.month=_bucket()
        if self.year_key and self.year_key != y: self.year=_bucket()
        self.day_key,self.month_key,self.year_key=d,m,y

    @staticmethod
    def _add(bucket: dict[str,Any], key: str, value: float) -> None:
        bucket[key]=float(bucket.get(key,0.0))+max(float(value),0.0)

    @staticmethod
    def _add_signed(bucket: dict[str,Any], key: str, value: float) -> None:
        """Ajoute une valeur financière signée sans effacer les prix négatifs."""
        bucket[key]=float(bucket.get(key,0.0))+float(value)

    @staticmethod
    def _add_appliance(bucket: dict[str,Any], aid: str, name: str, energy: float,
                       solar: float, grid: float, cost: float) -> None:
        apps=bucket.setdefault("appliances",{})
        a=apps.setdefault(aid,{"name":name,"energy_kwh":0.0,"solar_kwh":0.0,
                               "grid_kwh":0.0,"cost_eur":0.0,"hp_kwh":0.0,"hc_kwh":0.0})
        a["name"]=name
        a["energy_kwh"]+=max(energy,0.0)
        a["solar_kwh"]+=max(solar,0.0)
        a["grid_kwh"]+=max(grid,0.0)
        a["cost_eur"]+=max(cost,0.0)

    def process(self, snapshot: Any, prices: dict[str,Any],
                appliances: list[dict[str,Any]]) -> bool:
        """Intègre une vraie trame valide. Retourne True si une sauvegarde est souhaitée."""
        now=snapshot.timestamp
        self._rollover(now)
        if not snapshot.valid:
            self.last_valid_ts=None
            return False

        if self.last_valid_ts is None:
            self.last_valid_ts=now
            return False

        dt=(now-self.last_valid_ts).total_seconds()
        self.last_valid_ts=now

        # Une trame normale vaut ~30 s. Ne jamais comptabiliser un trou/reset/restart.
        if dt <= 0 or dt > 90:
            return False

        hours=dt/3600.0
        house=max(snapshot.house_w,0.0)/1000*hours
        pv=max(snapshot.pv_w,0.0)/1000*hours
        exported=max(snapshot.export_w,0.0)/1000*hours
        imported=max(snapshot.import_w,0.0)/1000*hours
        self_used=max(min(snapshot.pv_w,snapshot.house_w),0.0)/1000*hours

        period = str(prices.get("period", "HC"))
        buy=prices.get("active_buy")
        sell=prices.get("export_value")
        buy=float(buy) if isinstance(buy,(int,float)) else None
        sell=float(sell) if isinstance(sell,(int,float)) else None
        import_cost=imported*buy if buy is not None else 0.0
        # Convention financière FoxCat : sell > 0 = revenu, sell < 0 = coût.
        # On sépare explicitement les deux afin que l'Accounting ne perde plus
        # les périodes où l'utilisateur paie pour réinjecter.
        export_revenue=exported*max(sell,0.0) if sell is not None else 0.0
        export_cost=exported*max(-sell,0.0) if sell is not None else 0.0
        avoided=self_used*buy if buy is not None else 0.0

        for b in (self.today,self.month,self.year,self.lifetime):
            for k,v in (("house_kwh",house),("pv_kwh",pv),("self_consumed_kwh",self_used),
                        ("export_kwh",exported),("import_kwh",imported),
                        ("export_value_eur",export_revenue),
                        ("export_revenue_eur",export_revenue),
                        ("export_cost_eur",export_cost)):
                self._add(b,k,v)
            # Les prix dynamiques peuvent être négatifs. Un prélèvement à prix
            # négatif doit donc diminuer le coût cumulé au lieu d'être écrasé.
            self._add_signed(b,"import_cost_eur",import_cost)
            self._add_signed(b,"solar_avoided_cost_eur",avoided)

        solar_fraction=min(max(self_used/house if house>0 else 0.0,0.0),1.0)
        for app in appliances:
            power=app.get("power_w")
            if not isinstance(power,(int,float)) or power < 0:
                continue
            e=power/1000*hours
            solar=e*solar_fraction
            grid=e-solar
            cost=grid*buy if buy is not None else 0.0
            for b in (self.today,self.month,self.year,self.lifetime):
                aid=str(app["id"])
                name=str(app["name"])
                self._add_appliance(b,aid,name,e,solar,grid,cost)
                rec=b.setdefault("appliances",{}).setdefault(
                    aid, {"name":name,"energy_kwh":0.0,"solar_kwh":0.0,
                          "grid_kwh":0.0,"cost_eur":0.0,"hp_kwh":0.0,"hc_kwh":0.0}
                )
                key="hp_kwh" if period == "HP" else "hc_kwh"
                rec[key]=float(rec.get(key,0.0))+max(e,0.0)

        if self.last_save_ts is None or (now-self.last_save_ts).total_seconds() >= 300:
            self.last_save_ts=now
            return True
        return False

    @staticmethod
    def _view(b: dict[str,Any]) -> dict[str,Any]:
        pv=float(b.get("pv_kwh",0)); house=float(b.get("house_kwh",0))
        selfuse=float(b.get("self_consumed_kwh",0))
        imp=float(b.get("import_kwh",0)); exp=float(b.get("export_kwh",0))
        cost=float(b.get("import_cost_eur",0))
        # Les buckets restaurés depuis <=1.6.157 ne possèdent pas encore les
        # nouveaux champs : export_value_eur contenait alors le revenu brut.
        revenue=float(b.get("export_revenue_eur", b.get("export_value_eur",0)))
        export_cost=float(b.get("export_cost_eur",0))
        avoided=float(b.get("solar_avoided_cost_eur",0))
        return {
            **b,
            "export_value_eur": revenue,
            "export_revenue_eur": revenue,
            "export_cost_eur": export_cost,
            "autoconsumption_pct": (100*selfuse/pv) if pv>0 else 0.0,
            "autonomy_pct": (100*selfuse/house) if house>0 else 0.0,
            "solar_coverage_pct": (100*selfuse/house) if house>0 else 0.0,
            "grid_share_pct": (100*imp/house) if house>0 else 0.0,
            # Solde financier réel : achats + coût d'export - revenus d'export.
            "net_grid_cost_eur": cost + export_cost - revenue,
            "net_export_value_eur": revenue - export_cost,
            "solar_gain_eur": avoided + revenue - export_cost,
        }

    def view(self) -> dict[str,Any]:
        return {
            "today":self._view(deepcopy(self.today)),
            "month":self._view(deepcopy(self.month)),
            "year":self._view(deepcopy(self.year)),
            "lifetime":self._view(deepcopy(self.lifetime)),
        }
