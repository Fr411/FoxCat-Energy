from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


ZERO = {
    "house_kwh": 0.0,
    "pv_kwh": 0.0,
    "self_consumed_kwh": 0.0,
    "export_kwh": 0.0,
    "import_kwh": 0.0,
    "import_cost_eur": 0.0,
    # Compatibilité historique : solde signé de la réinjection.
    "export_value_eur": 0.0,
    "export_revenue_eur": 0.0,
    "export_cost_eur": 0.0,
    "solar_avoided_cost_eur": 0.0,
}

RATE_ZERO = {
    "import_kwh": 0.0,
    "export_kwh": 0.0,
    "import_cost_eur": 0.0,
    "export_revenue_eur": 0.0,
    "export_cost_eur": 0.0,
}


def _rate_bucket() -> dict[str, float]:
    return dict(RATE_ZERO)


def _tariff_bucket() -> dict[str, Any]:
    return {
        "dynamic": _rate_bucket(),
        "hphc": {"HP": _rate_bucket(), "HC": _rate_bucket()},
        "other": _rate_bucket(),
    }


def _bucket() -> dict[str, Any]:
    return {**ZERO, "appliances": {}, "tariff": _tariff_bucket()}


class EnergyAccounting:
    """Ledger énergétique et financier FoxCat.

    V1.6.159 sépare définitivement la vérité physique (kWh) de sa valorisation
    financière. Une réinjection ne diminue jamais un compteur d'import et un
    revenu d'export n'est jamais converti en kWh.
    """

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
        self.breakdown_since: str | None = None

    @staticmethod
    def _migrate_rate(raw: Any) -> dict[str, float]:
        result = _rate_bucket()
        if isinstance(raw, dict):
            for key in result:
                try:
                    result[key] = float(raw.get(key, result[key]) or 0.0)
                except (TypeError, ValueError):
                    result[key] = 0.0
        return result

    @classmethod
    def _migrate_bucket(cls, raw: Any) -> dict[str, Any]:
        result = _bucket()
        if not isinstance(raw, dict):
            return result
        for key in ZERO:
            try:
                result[key] = float(raw.get(key, result[key]) or 0.0)
            except (TypeError, ValueError):
                result[key] = 0.0

        # Stores <= 1.6.157 : export_value_eur était un revenu brut positif.
        if "export_revenue_eur" not in raw and "export_cost_eur" not in raw:
            old_value = float(raw.get("export_value_eur", 0.0) or 0.0)
            result["export_revenue_eur"] = max(old_value, 0.0)
            result["export_cost_eur"] = max(-old_value, 0.0)
        else:
            result["export_revenue_eur"] = float(raw.get("export_revenue_eur", 0.0) or 0.0)
            result["export_cost_eur"] = float(raw.get("export_cost_eur", 0.0) or 0.0)

        apps = raw.get("appliances")
        result["appliances"] = deepcopy(apps) if isinstance(apps, dict) else {}
        tariff = raw.get("tariff") if isinstance(raw.get("tariff"), dict) else {}
        hphc = tariff.get("hphc") if isinstance(tariff.get("hphc"), dict) else {}
        result["tariff"] = {
            "dynamic": cls._migrate_rate(tariff.get("dynamic")),
            "hphc": {
                "HP": cls._migrate_rate(hphc.get("HP")),
                "HC": cls._migrate_rate(hphc.get("HC")),
            },
            "other": cls._migrate_rate(tariff.get("other")),
        }
        return result

    def restore(self, raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        self.day_key = str(raw.get("day_key", ""))
        self.month_key = str(raw.get("month_key", ""))
        self.year_key = str(raw.get("year_key", ""))
        self.breakdown_since = str(raw.get("breakdown_since") or "") or None
        for name in ("today", "month", "year", "lifetime"):
            setattr(self, name, self._migrate_bucket(raw.get(name)))
        self.last_valid_ts = None  # Ne jamais intégrer le downtime HA.

    def dump(self) -> dict[str, Any]:
        return {
            "schema": 2,
            "day_key": self.day_key,
            "month_key": self.month_key,
            "year_key": self.year_key,
            "breakdown_since": self.breakdown_since,
            "today": self.today,
            "month": self.month,
            "year": self.year,
            "lifetime": self.lifetime,
        }

    def _rollover(self, now: datetime) -> None:
        d, m, y = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"), now.strftime("%Y")
        if self.day_key and self.day_key != d:
            self.today = _bucket()
        if self.month_key and self.month_key != m:
            self.month = _bucket()
        if self.year_key and self.year_key != y:
            self.year = _bucket()
        self.day_key, self.month_key, self.year_key = d, m, y

    @staticmethod
    def _add(bucket: dict[str, Any], key: str, value: float) -> None:
        bucket[key] = float(bucket.get(key, 0.0)) + max(float(value), 0.0)

    @staticmethod
    def _add_signed(bucket: dict[str, Any], key: str, value: float) -> None:
        bucket[key] = float(bucket.get(key, 0.0)) + float(value)

    @staticmethod
    def _tariff_target(bucket: dict[str, Any], regime: str, period: str) -> dict[str, Any]:
        tariff = bucket.setdefault("tariff", _tariff_bucket())
        if regime == "Dynamique":
            return tariff.setdefault("dynamic", _rate_bucket())
        if regime == "Bi-horaire HP/HC":
            hphc = tariff.setdefault("hphc", {"HP": _rate_bucket(), "HC": _rate_bucket()})
            return hphc.setdefault("HP" if period == "HP" else "HC", _rate_bucket())
        return tariff.setdefault("other", _rate_bucket())

    @classmethod
    def _add_tariff(
        cls,
        bucket: dict[str, Any],
        *,
        regime: str,
        period: str,
        imported: float,
        exported: float,
        import_cost: float,
        export_revenue: float,
        export_cost: float,
    ) -> None:
        target = cls._tariff_target(bucket, regime, period)
        cls._add(target, "import_kwh", imported)
        cls._add(target, "export_kwh", exported)
        cls._add_signed(target, "import_cost_eur", import_cost)
        cls._add(target, "export_revenue_eur", export_revenue)
        cls._add(target, "export_cost_eur", export_cost)

    @staticmethod
    def _add_appliance(
        bucket: dict[str, Any],
        aid: str,
        name: str,
        energy: float,
        solar: float,
        grid: float,
        cost: float,
        regime: str,
        period: str,
    ) -> None:
        apps = bucket.setdefault("appliances", {})
        a = apps.setdefault(
            aid,
            {
                "name": name,
                "energy_kwh": 0.0,
                "solar_kwh": 0.0,
                "grid_kwh": 0.0,
                "cost_eur": 0.0,
                "hp_kwh": 0.0,
                "hc_kwh": 0.0,
                "dynamic_kwh": 0.0,
                "other_kwh": 0.0,
            },
        )
        a["name"] = name
        a["energy_kwh"] = float(a.get("energy_kwh", 0.0)) + max(energy, 0.0)
        a["solar_kwh"] = float(a.get("solar_kwh", 0.0)) + max(solar, 0.0)
        a["grid_kwh"] = float(a.get("grid_kwh", 0.0)) + max(grid, 0.0)
        # Le coût est signé : un prix d'achat négatif doit rester négatif.
        a["cost_eur"] = float(a.get("cost_eur", 0.0)) + float(cost)
        if regime == "Dynamique":
            key = "dynamic_kwh"
        elif regime == "Bi-horaire HP/HC":
            key = "hp_kwh" if period == "HP" else "hc_kwh"
        else:
            key = "other_kwh"
        a[key] = float(a.get(key, 0.0)) + max(energy, 0.0)

    def process(self, snapshot: Any, prices: dict[str, Any], appliances: list[dict[str, Any]]) -> bool:
        """Intègre une vraie trame valide et sa valeur tarifaire au même instant."""
        now = snapshot.timestamp
        self._rollover(now)
        if not snapshot.valid:
            self.last_valid_ts = None
            return False
        if self.last_valid_ts is None:
            self.last_valid_ts = now
            return False

        dt = (now - self.last_valid_ts).total_seconds()
        self.last_valid_ts = now
        if dt <= 0 or dt > 90:
            return False
        if self.breakdown_since is None:
            self.breakdown_since = now.isoformat()

        hours = dt / 3600.0
        house = max(snapshot.house_w, 0.0) / 1000.0 * hours
        pv = max(snapshot.pv_w, 0.0) / 1000.0 * hours
        exported = max(snapshot.export_w, 0.0) / 1000.0 * hours
        imported = max(snapshot.import_w, 0.0) / 1000.0 * hours
        self_used = max(min(snapshot.pv_w, snapshot.house_w), 0.0) / 1000.0 * hours

        regime = str(prices.get("regime") or "AUTRE")
        period = str(prices.get("period") or "HC")
        buy = prices.get("active_buy")
        sell = prices.get("export_value")
        buy = float(buy) if isinstance(buy, (int, float)) else None
        sell = float(sell) if isinstance(sell, (int, float)) else None
        import_cost = imported * buy if buy is not None else 0.0
        export_net_value = exported * sell if sell is not None else 0.0
        export_revenue = max(export_net_value, 0.0)
        export_cost = max(-export_net_value, 0.0)
        avoided = self_used * buy if buy is not None else 0.0

        for bucket in (self.today, self.month, self.year, self.lifetime):
            for key, value in (
                ("house_kwh", house),
                ("pv_kwh", pv),
                ("self_consumed_kwh", self_used),
                ("export_kwh", exported),
                ("import_kwh", imported),
                ("export_revenue_eur", export_revenue),
                ("export_cost_eur", export_cost),
            ):
                self._add(bucket, key, value)
            self._add_signed(bucket, "import_cost_eur", import_cost)
            self._add_signed(bucket, "export_value_eur", export_net_value)
            self._add_signed(bucket, "solar_avoided_cost_eur", avoided)
            self._add_tariff(
                bucket,
                regime=regime,
                period=period,
                imported=imported,
                exported=exported,
                import_cost=import_cost,
                export_revenue=export_revenue,
                export_cost=export_cost,
            )

        solar_fraction = min(max(self_used / house if house > 0 else 0.0, 0.0), 1.0)
        for app in appliances:
            power = app.get("power_w")
            if not isinstance(power, (int, float)) or power < 0:
                continue
            energy = power / 1000.0 * hours
            solar = energy * solar_fraction
            grid = energy - solar
            cost = grid * buy if buy is not None else 0.0
            aid = str(app["id"])
            name = str(app["name"])
            for bucket in (self.today, self.month, self.year, self.lifetime):
                self._add_appliance(bucket, aid, name, energy, solar, grid, cost, regime, period)

        if self.last_save_ts is None or (now - self.last_save_ts).total_seconds() >= 300:
            self.last_save_ts = now
            return True
        return False

    @staticmethod
    def _view_rate(rate: dict[str, Any]) -> dict[str, Any]:
        imp = float(rate.get("import_kwh", 0.0) or 0.0)
        exp = float(rate.get("export_kwh", 0.0) or 0.0)
        cost = float(rate.get("import_cost_eur", 0.0) or 0.0)
        revenue = float(rate.get("export_revenue_eur", 0.0) or 0.0)
        export_cost = float(rate.get("export_cost_eur", 0.0) or 0.0)
        return {
            **rate,
            "import_kwh": imp,
            "export_kwh": exp,
            "import_cost_eur": cost,
            "export_revenue_eur": revenue,
            "export_cost_eur": export_cost,
            "net_cost_eur": cost + export_cost - revenue,
            "net_export_value_eur": revenue - export_cost,
        }

    @classmethod
    def _view(cls, bucket: dict[str, Any]) -> dict[str, Any]:
        pv = float(bucket.get("pv_kwh", 0.0) or 0.0)
        house = float(bucket.get("house_kwh", 0.0) or 0.0)
        selfuse = float(bucket.get("self_consumed_kwh", 0.0) or 0.0)
        imp = float(bucket.get("import_kwh", 0.0) or 0.0)
        cost = float(bucket.get("import_cost_eur", 0.0) or 0.0)
        value = float(bucket.get("export_value_eur", 0.0) or 0.0)
        revenue = float(bucket.get("export_revenue_eur", max(value, 0.0)) or 0.0)
        export_cost = float(bucket.get("export_cost_eur", max(-value, 0.0)) or 0.0)
        avoided = float(bucket.get("solar_avoided_cost_eur", 0.0) or 0.0)
        tariff = bucket.get("tariff") if isinstance(bucket.get("tariff"), dict) else _tariff_bucket()
        hphc = tariff.get("hphc") if isinstance(tariff.get("hphc"), dict) else {}
        tariff_view = {
            "dynamic": cls._view_rate(tariff.get("dynamic") or {}),
            "hphc": {
                "HP": cls._view_rate(hphc.get("HP") or {}),
                "HC": cls._view_rate(hphc.get("HC") or {}),
            },
            "other": cls._view_rate(tariff.get("other") or {}),
        }
        return {
            **bucket,
            "tariff": tariff_view,
            "export_revenue_eur": revenue,
            "export_cost_eur": export_cost,
            "autoconsumption_pct": (100.0 * selfuse / pv) if pv > 0 else 0.0,
            "autonomy_pct": (100.0 * selfuse / house) if house > 0 else 0.0,
            "solar_coverage_pct": (100.0 * selfuse / house) if house > 0 else 0.0,
            "grid_share_pct": (100.0 * imp / house) if house > 0 else 0.0,
            "net_grid_cost_eur": cost + export_cost - revenue,
            "net_export_value_eur": revenue - export_cost,
            "solar_gain_eur": avoided + revenue - export_cost,
        }

    def view(self) -> dict[str, Any]:
        return {
            "schema": 2,
            "breakdown_since": self.breakdown_since,
            "today": self._view(deepcopy(self.today)),
            "month": self._view(deepcopy(self.month)),
            "year": self._view(deepcopy(self.year)),
            "lifetime": self._view(deepcopy(self.lifetime)),
        }
