"""Calcul pur de l'intensité réseau, du taux de charge du disjoncteur et de la décharge d'écrêtage.

Aucun import Home Assistant : le coordinateur lit les mesures, appelle ces
fonctions et publie le résultat. Aucune commande physique n'est émise ici.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

GRID_REGIME_MONO = "MONO"
GRID_REGIME_TRI = "TRI"
GRID_REGIME_TETRA = "TETRA"
GRID_REGIMES = (GRID_REGIME_MONO, GRID_REGIME_TRI, GRID_REGIME_TETRA)

CONF_GRID_REGIME = "grid_regime"
CONF_INVERTER_COS_PHI = "inverter_cos_phi"
CONF_GRID_VOLTAGE_SENSOR = "grid_voltage_sensor"
CONF_GRID_CURRENT_L1_SENSOR = "grid_current_l1_sensor"
CONF_GRID_CURRENT_L2_SENSOR = "grid_current_l2_sensor"
CONF_GRID_CURRENT_L3_SENSOR = "grid_current_l3_sensor"
PHASE_CURRENT_KEYS = (
    CONF_GRID_CURRENT_L1_SENSOR,
    CONF_GRID_CURRENT_L2_SENSOR,
    CONF_GRID_CURRENT_L3_SENSOR,
)

DEFAULT_COS_PHI = 1.0
MIN_COS_PHI = 0.1
DEFAULT_VOLTAGE_V = 230.0
SQRT3 = math.sqrt(3.0)

SOURCE_PHASES = "phases"
SOURCE_POWER = "power"


def normalize_regime(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text in GRID_REGIMES else GRID_REGIME_MONO


def clamp_cos_phi(value: Any) -> float:
    try:
        cos_phi = float(value)
    except (TypeError, ValueError):
        return DEFAULT_COS_PHI
    if not math.isfinite(cos_phi) or cos_phi <= 0.0:
        return DEFAULT_COS_PHI
    return max(MIN_COS_PHI, min(1.0, cos_phi))


def line_voltage_v(regime: str, voltage_v: float) -> float:
    """Tension composée : une mesure < 300 V est une tension simple (×√3), sinon déjà composée."""
    return voltage_v * SQRT3 if voltage_v < 300.0 else voltage_v


def current_a(
    regime: str,
    *,
    power_w: float,
    voltage_v: float,
    cos_phi: float,
    phase_currents_a: Sequence[float | None] = (),
) -> tuple[float, str]:
    """Intensité de référence (A) et source utilisée.

    MONO : I = P / (U × cos φ).
    TRI/TETRA : maximum des intensités de phase mesurées, sinon
    I = P / (√3 × U_composée × cos φ).
    """
    regime = normalize_regime(regime)
    cos_phi = clamp_cos_phi(cos_phi)
    power_w = abs(power_w)
    if voltage_v <= 0.0 or not math.isfinite(voltage_v):
        voltage_v = DEFAULT_VOLTAGE_V
    if regime == GRID_REGIME_MONO:
        return power_w / (voltage_v * cos_phi), SOURCE_POWER
    measured = [abs(v) for v in phase_currents_a if v is not None and math.isfinite(v)]
    if measured:
        return max(measured), SOURCE_PHASES
    u_line = line_voltage_v(regime, voltage_v)
    return power_w / (SQRT3 * u_line * cos_phi), SOURCE_POWER


@dataclass(frozen=True, slots=True)
class GridLoad:
    regime: str
    voltage_v: float
    cos_phi: float
    current_a: float
    breaker_a: float
    load_pct: float | None
    limit_pct: float
    excess_a: float
    discharge_w: float
    source: str
    exceeded: bool


def evaluate(
    regime: Any,
    *,
    power_w: float,
    voltage_v: float,
    cos_phi: Any,
    breaker_a: float,
    limit_pct: float,
    enabled: bool = True,
    phase_currents_a: Sequence[float | None] = (),
    max_discharge_w: float | None = None,
) -> GridLoad:
    """Taux de charge du disjoncteur et puissance de décharge à demander à la batterie.

    L'excédent (A au-dessus du seuil) est converti en watts avec la même formule
    que l'intensité : P = I × U × cos φ (MONO) ou I × √3 × U_composée × cos φ (TRI/TETRA).
    """
    regime = normalize_regime(regime)
    cos = clamp_cos_phi(cos_phi)
    volt = voltage_v if voltage_v and voltage_v > 0.0 and math.isfinite(voltage_v) else DEFAULT_VOLTAGE_V
    amps, source = current_a(regime, power_w=power_w, voltage_v=volt, cos_phi=cos, phase_currents_a=phase_currents_a)
    limit_pct = max(0.0, min(100.0, limit_pct))
    if breaker_a <= 0.0:
        return GridLoad(regime, volt, cos, amps, breaker_a, None, limit_pct, 0.0, 0.0, source, False)
    load_pct = amps / breaker_a * 100.0
    threshold_a = breaker_a * limit_pct / 100.0
    excess = max(0.0, amps - threshold_a) if enabled else 0.0
    if regime == GRID_REGIME_MONO:
        discharge = excess * volt * cos
    else:
        discharge = excess * SQRT3 * line_voltage_v(regime, volt) * cos
    if max_discharge_w is not None:
        discharge = min(discharge, max(0.0, max_discharge_w))
    return GridLoad(
        regime, volt, cos, amps, breaker_a, load_pct, limit_pct, excess, discharge, source,
        enabled and excess > 0.0,
    )


def as_dict(result: GridLoad) -> Mapping[str, Any]:
    return {
        "regime": result.regime,
        "voltage_v": round(result.voltage_v, 1),
        "cos_phi": round(result.cos_phi, 3),
        "current_a": round(result.current_a, 2),
        "breaker_a": result.breaker_a,
        "load_pct": None if result.load_pct is None else round(result.load_pct, 1),
        "limit_pct": result.limit_pct,
        "excess_a": round(result.excess_a, 2),
        "discharge_w": round(result.discharge_w, 0),
        "source": result.source,
        "exceeded": result.exceeded,
    }
