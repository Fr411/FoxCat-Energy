"""Types communs du module Virtual Assets (lecture seule, aucune commande physique)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VirtualAssetsError(ValueError):
    """Erreur de validation du module Virtual Assets."""


class DataQuality(str, Enum):
    """Provenance d'une donnée : jamais mélangée silencieusement."""

    MEASURED = "measured"
    SIMULATED = "simulated"
    ESTIMATED = "estimated"
    MISSING = "missing"


def require_number(name: str, value: object, *, minimum: float | None = None,
                   maximum: float | None = None, exclusive_min: bool = False) -> float:
    """Valide un nombre fini (bool refusé) et ses bornes."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise VirtualAssetsError(f"{name} doit être un nombre fini")
    value = float(value)
    if minimum is not None and (value <= minimum if exclusive_min else value < minimum):
        raise VirtualAssetsError(f"{name} trop bas : {value}")
    if maximum is not None and value > maximum:
        raise VirtualAssetsError(f"{name} trop haut : {value}")
    return value


@dataclass(frozen=True, slots=True)
class Slot:
    """Un pas de temps. Les valeurs ``None`` signifient « donnée manquante »."""

    start: datetime
    hours: float
    load_kwh: float | None
    pv_kwh: float | None
    import_price: float | None = None
    export_price: float | None = None
    load_quality: DataQuality = DataQuality.MEASURED
    pv_quality: DataQuality = DataQuality.MEASURED
    price_quality: DataQuality = DataQuality.MEASURED
    # True : prix futur (estimé), utilisable pour planifier mais pas pour comptabiliser du réalisé
    price_is_future: bool = False

    def __post_init__(self) -> None:
        require_number("hours", self.hours, minimum=0, exclusive_min=True)
        for name in ("load_kwh", "pv_kwh"):
            value = getattr(self, name)
            if value is not None:
                require_number(name, value, minimum=0)
        for name in ("import_price", "export_price"):
            value = getattr(self, name)
            if value is not None:
                require_number(name, value)


@dataclass(frozen=True, slots=True)
class SlotFlow:
    """Résultat simulé d'un pas (kWh côté réseau/maison)."""

    start: datetime
    hours: float
    action: str
    reasons: tuple[str, ...]
    load_kwh: float
    pv_kwh: float
    battery_charge_kwh: float          # énergie prélevée côté AC
    battery_charge_from_grid_kwh: float
    battery_discharge_kwh: float       # énergie délivrée côté AC
    ev_charge_kwh: float               # énergie prélevée côté AC
    ev_charge_from_grid_kwh: float
    import_kwh: float
    export_kwh: float
    soc_battery_kwh: float
    soc_ev_kwh: float
    import_price: float | None
    export_price: float | None
    quality: DataQuality = DataQuality.SIMULATED
    price_quality: DataQuality = DataQuality.MISSING
