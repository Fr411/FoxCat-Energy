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
# Tensions : phase-neutre (≈ 230 V) et entre lignes (≈ 400 V). Facultatives.
CONF_GRID_VOLTAGE_L1_SENSOR = "grid_voltage_l1_sensor"
CONF_GRID_VOLTAGE_L2_SENSOR = "grid_voltage_l2_sensor"
CONF_GRID_VOLTAGE_L3_SENSOR = "grid_voltage_l3_sensor"
CONF_GRID_LINE_VOLTAGE_L12_SENSOR = "grid_line_voltage_l12_sensor"
CONF_GRID_LINE_VOLTAGE_L23_SENSOR = "grid_line_voltage_l23_sensor"
CONF_GRID_LINE_VOLTAGE_L31_SENSOR = "grid_line_voltage_l31_sensor"
PHASE_VOLTAGE_KEYS = (
    CONF_GRID_VOLTAGE_L1_SENSOR,
    CONF_GRID_VOLTAGE_L2_SENSOR,
    CONF_GRID_VOLTAGE_L3_SENSOR,
)
LINE_VOLTAGE_KEYS = (
    CONF_GRID_LINE_VOLTAGE_L12_SENSOR,
    CONF_GRID_LINE_VOLTAGE_L23_SENSOR,
    CONF_GRID_LINE_VOLTAGE_L31_SENSOR,
)
# Sans mesure du courant par phase, la phase la plus chargée est inconnue : ce coefficient
# (>= 1) majore l'intensité moyenne estimée pour couvrir un déséquilibre.
CONF_PHASE_IMBALANCE_FACTOR = "grid_phase_imbalance_factor"
DEFAULT_IMBALANCE_FACTOR = 1.0
MAX_IMBALANCE_FACTOR = 3.0

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

# Plages plausibles : écartent une mesure aberrante (capteur figé, mauvaise unité).
PHASE_VOLTAGE_RANGE_V = (100.0, 300.0)
LINE_VOLTAGE_RANGE_V = (170.0, 520.0)

VOLTAGE_NOMINAL = "nominal"
VOLTAGE_PHASE = "phase"
VOLTAGE_LINE = "line"
VOLTAGE_BOTH = "phase+line"


def clamp_imbalance_factor(value: Any) -> float:
    try:
        factor = float(value)
    except (TypeError, ValueError):
        return DEFAULT_IMBALANCE_FACTOR
    if not math.isfinite(factor) or factor < 1.0:
        return DEFAULT_IMBALANCE_FACTOR
    return min(MAX_IMBALANCE_FACTOR, factor)


@dataclass(frozen=True, slots=True)
class VoltageInfo:
    """Tension phase-neutre utilisée pour les calculs, et son origine."""

    phase_v: float
    line_v: float
    source: str
    spread_pct: float | None


def _valid(values: Sequence[float | None], low: float, high: float) -> list[float]:
    return [v for v in values if v is not None and math.isfinite(v) and low <= v <= high]


def resolve_voltages(
    nominal_v: float,
    *,
    phase_v: Sequence[float | None] = (),
    line_v: Sequence[float | None] = (),
) -> VoltageInfo:
    """Tension de calcul à partir des mesures disponibles, sinon de la tension nominale.

    Tensions phase-neutre et entre lignes sont recoupées : si les deux existent, la tension de
    phase retenue est la moyenne des deux estimations (U_ligne / √3 et V_phase). Si une seule
    famille est mesurée, l'autre en est déduite. ``spread_pct`` est l'écart (max - min) / moyenne
    des tensions de phase : un indicateur de santé du réseau, pas une mesure de courant.
    """
    phases = _valid(phase_v, *PHASE_VOLTAGE_RANGE_V)
    lines = _valid(line_v, *LINE_VOLTAGE_RANGE_V)
    nominal = nominal_v if nominal_v and math.isfinite(nominal_v) and nominal_v > 0.0 else DEFAULT_VOLTAGE_V
    if nominal >= 300.0:
        nominal = nominal / SQRT3
    spread = None
    if phases:
        mean_phase = sum(phases) / len(phases)
        if len(phases) > 1 and mean_phase > 0.0:
            spread = (max(phases) - min(phases)) / mean_phase * 100.0
    if phases and lines:
        mean_line = sum(lines) / len(lines)
        v = (sum(phases) / len(phases) + mean_line / SQRT3) / 2.0
        return VoltageInfo(v, v * SQRT3, VOLTAGE_BOTH, spread)
    if phases:
        v = sum(phases) / len(phases)
        return VoltageInfo(v, v * SQRT3, VOLTAGE_PHASE, spread)
    if lines:
        v = sum(lines) / len(lines) / SQRT3
        return VoltageInfo(v, v * SQRT3, VOLTAGE_LINE, spread)
    return VoltageInfo(nominal, nominal * SQRT3, VOLTAGE_NOMINAL, None)


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
    imbalance_factor: float = DEFAULT_IMBALANCE_FACTOR,
) -> tuple[float, str]:
    """Intensité de référence (A) et source utilisée.

    MONO : I = P / (U × cos φ).
    TRI/TETRA : maximum des intensités de phase mesurées, sinon
    I = P / (√3 × U_composée × cos φ) × coefficient de déséquilibre (phase la plus chargée).
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
    return power_w / (SQRT3 * u_line * cos_phi) * clamp_imbalance_factor(imbalance_factor), SOURCE_POWER


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
    imbalance_factor: float = DEFAULT_IMBALANCE_FACTOR


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
    imbalance_factor: float = DEFAULT_IMBALANCE_FACTOR,
) -> GridLoad:
    """Taux de charge du disjoncteur et puissance de décharge à demander à la batterie.

    L'excédent (A au-dessus du seuil) est converti en watts avec la même formule
    que l'intensité : P = I × U × cos φ (MONO) ou I × √3 × U_composée × cos φ (TRI/TETRA).
    """
    regime = normalize_regime(regime)
    cos = clamp_cos_phi(cos_phi)
    volt = voltage_v if voltage_v and voltage_v > 0.0 and math.isfinite(voltage_v) else DEFAULT_VOLTAGE_V
    factor = clamp_imbalance_factor(imbalance_factor)
    amps, source = current_a(
        regime, power_w=power_w, voltage_v=volt, cos_phi=cos, phase_currents_a=phase_currents_a,
        imbalance_factor=factor,
    )
    limit_pct = max(0.0, min(100.0, limit_pct))
    if breaker_a <= 0.0:
        return GridLoad(regime, volt, cos, amps, breaker_a, None, limit_pct, 0.0, 0.0, source, False, factor)
    load_pct = amps / breaker_a * 100.0
    threshold_a = breaker_a * limit_pct / 100.0
    excess = max(0.0, amps - threshold_a) if enabled else 0.0
    # La puissance à décharger est celle qui ramène la phase la plus chargée sous le seuil : on
    # retire le coefficient pour repasser de l'intensité majorée à la puissance réellement mesurée.
    if regime == GRID_REGIME_MONO:
        discharge = excess * volt * cos
    else:
        discharge = excess * SQRT3 * line_voltage_v(regime, volt) * cos / (
            factor if source == SOURCE_POWER else 1.0
        )
    if max_discharge_w is not None:
        discharge = min(discharge, max(0.0, max_discharge_w))
    return GridLoad(
        regime, volt, cos, amps, breaker_a, load_pct, limit_pct, excess, discharge, source,
        enabled and excess > 0.0, factor,
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
        "imbalance_factor": result.imbalance_factor,
    }
