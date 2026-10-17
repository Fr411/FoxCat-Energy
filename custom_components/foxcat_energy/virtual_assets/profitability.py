"""Rentabilité : ROI, retour sur investissement, VAN, dégradation, sensibilité remplacement.

Chaque indicateur vaut ``None`` si une donnée requise manque (jamais inventée) ; les
hypothèses utilisées sont listées dans ``assumptions``. Valeurs de qualité ``estimated``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .models import VirtualAssetsError, require_number

MIN_PERIOD_DAYS = 7.0


@dataclass(frozen=True, slots=True)
class ProfitabilityInputs:
    savings_eur: float | None            # économie simulée sur la période (prix mesurés)
    period_days: float | None
    capex_eur: float | None
    years: int = 10
    discount_rate: float = 0.04
    degradation_pct_per_year: float | None = None
    replacement_cost_eur: float | None = None
    replacement_year: int | None = None
    sensitivity_factors: Sequence[float] = (0.5, 1.0, 1.5)

    def __post_init__(self) -> None:
        if isinstance(self.years, bool) or not isinstance(self.years, int) or self.years < 1:
            raise VirtualAssetsError("years doit être un entier >= 1")
        require_number("discount_rate", self.discount_rate, minimum=0)
        for n in ("capex_eur", "replacement_cost_eur"):
            v = getattr(self, n)
            if v is not None:
                require_number(n, v, minimum=0)
        if self.degradation_pct_per_year is not None:
            require_number("degradation_pct_per_year", self.degradation_pct_per_year,
                           minimum=0, maximum=100)
        if self.savings_eur is not None:
            require_number("savings_eur", self.savings_eur)
        if self.period_days is not None:
            require_number("period_days", self.period_days, minimum=0, exclusive_min=True)


def _cashflows(annual: float, deg_pct: float, years: int) -> list[float]:
    return [annual * (1 - deg_pct / 100.0) ** y for y in range(years)]


def _npv(flows: list[float], rate: float, capex: float, repl_cost: float | None,
         repl_year: int | None) -> float:
    npv = -capex + sum(f / (1 + rate) ** (i + 1) for i, f in enumerate(flows))
    if repl_cost is not None and repl_year is not None and 1 <= repl_year <= len(flows):
        npv -= repl_cost / (1 + rate) ** repl_year
    return npv


def analyze_profitability(inp: ProfitabilityInputs) -> dict[str, Any]:
    out: dict[str, Any] = {"quality": "estimated", "annual_savings_eur": None, "roi": None,
                           "payback_years": None, "npv_eur": None,
                           "replacement_sensitivity": None, "assumptions": [], "missing": []}
    if inp.savings_eur is None or inp.period_days is None:
        out["missing"].append("simulated_savings")
    elif inp.period_days < MIN_PERIOD_DAYS:
        out["missing"].append(f"period_shorter_than_{int(MIN_PERIOD_DAYS)}_days")
    else:
        out["annual_savings_eur"] = inp.savings_eur * 365.0 / inp.period_days
        out["assumptions"].append("linear_annualisation_of_observed_period")
    if inp.capex_eur is None:
        out["missing"].append("capex")
    annual, capex = out["annual_savings_eur"], inp.capex_eur
    if annual is None or capex is None:
        return out
    deg = inp.degradation_pct_per_year
    if deg is None:
        deg = 0.0
        out["assumptions"].append("degradation_not_provided_assumed_0")
    flows = _cashflows(annual, deg, inp.years)
    total = sum(flows)
    out["degradation_pct_per_year"] = deg
    out["roi"] = (total - capex) / capex if capex > 0 else None
    out["npv_eur"] = _npv(flows, inp.discount_rate, capex, inp.replacement_cost_eur,
                          inp.replacement_year)
    cum = 0.0
    for i, f in enumerate(flows):
        if f > 0 and cum + f >= capex:
            out["payback_years"] = i + (capex - cum) / f
            break
        cum += f
    if capex == 0:
        out["payback_years"] = 0.0
    if inp.replacement_cost_eur is not None and inp.replacement_year is not None:
        out["replacement_sensitivity"] = {
            f: _npv(flows, inp.discount_rate, capex, inp.replacement_cost_eur * f,
                    inp.replacement_year) for f in inp.sensitivity_factors}
    else:
        out["missing"].append("replacement_cost_or_year")
    return out
