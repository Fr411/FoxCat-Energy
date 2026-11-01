"""Batterie domestique virtuelle : état d'énergie borné, aucune commande physique."""
from __future__ import annotations

from copy import copy

from .config import BatterySpec
from .models import VirtualAssetsError, require_number


class VirtualBattery:
    """Les flux « ac_kwh » sont côté AC ; ``soc_kwh`` est l'énergie stockée (côté cellule)."""

    __slots__ = ("spec", "soc_kwh", "discharged_cell_kwh", "charged_cell_kwh")

    def __init__(self, spec: BatterySpec, soc_pct: float | None = None) -> None:
        self.spec = spec
        pct = spec.reserve_soc_pct if soc_pct is None else require_number(
            "soc_pct", soc_pct, minimum=0, maximum=100)
        if not spec.min_soc_pct <= pct <= spec.max_soc_pct:
            raise VirtualAssetsError("soc_pct hors des limites min/max de la batterie")
        self.soc_kwh = spec.capacity_kwh * pct / 100.0
        self.discharged_cell_kwh = 0.0
        self.charged_cell_kwh = 0.0

    def clone(self) -> "VirtualBattery":
        other = copy(self)
        return other

    @property
    def min_kwh(self) -> float:
        return self.spec.capacity_kwh * self.spec.min_soc_pct / 100.0

    @property
    def max_kwh(self) -> float:
        return self.spec.capacity_kwh * self.spec.max_soc_pct / 100.0

    @property
    def reserve_kwh(self) -> float:
        return self.spec.capacity_kwh * self.spec.reserve_soc_pct / 100.0

    @property
    def soc_pct(self) -> float:
        return 100.0 * self.soc_kwh / self.spec.capacity_kwh

    @property
    def equivalent_cycles(self) -> float:
        return self.discharged_cell_kwh / self.spec.capacity_kwh

    def max_charge_ac(self, hours: float) -> float:
        room = max(self.max_kwh - self.soc_kwh, 0.0)
        return min(self.spec.max_charge_kw * hours, room / self.spec.charge_efficiency)

    def max_discharge_ac(self, hours: float, floor_kwh: float | None = None) -> float:
        floor = self.min_kwh if floor_kwh is None else max(floor_kwh, self.min_kwh)
        avail = max(self.soc_kwh - floor, 0.0)
        return min(self.spec.max_discharge_kw * hours, avail * self.spec.discharge_efficiency)

    def charge(self, ac_kwh: float, hours: float) -> float:
        """Charge ; retourne l'énergie AC réellement absorbée (limitée par puissance et capacité)."""
        require_number("ac_kwh", ac_kwh, minimum=0)
        used = min(ac_kwh, self.max_charge_ac(hours))
        stored = used * self.spec.charge_efficiency
        self.soc_kwh = min(self.soc_kwh + stored, self.max_kwh)
        self.charged_cell_kwh += stored
        return used

    def discharge(self, ac_kwh: float, hours: float, floor_kwh: float | None = None) -> float:
        """Décharge ; retourne l'énergie AC réellement délivrée (plancher = min ou réserve)."""
        require_number("ac_kwh", ac_kwh, minimum=0)
        out = min(ac_kwh, self.max_discharge_ac(hours, floor_kwh))
        cell = out / self.spec.discharge_efficiency
        self.soc_kwh = max(self.soc_kwh - cell, self.min_kwh)
        self.discharged_cell_kwh += cell
        return out

    def wear_cost_eur_per_kwh(self) -> float | None:
        """Coût d'usure par kWh délivré ; ``None`` si capex ou durée de vie inconnus."""
        s = self.spec
        if s.capex_eur is None or s.rated_throughput_kwh is None:
            return None
        return s.capex_eur / s.rated_throughput_kwh
