"""Logique pure de l'écrêtage de pointe (délestage haute consommation).

Aucun import Home Assistant : tout est testable unitairement. Le coordinateur
ne fait que lire la configuration, appeler ces fonctions et appliquer les actions.

Les valeurs par défaut reproduisent exactement le comportement historique
(FoxCat <= 1.7.6) : seuil à 90 % du disjoncteur, mesure sur la puissance maison,
1 trame de confirmation avec disjoncteur (2 sans), 5 trames de réarmement.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .const import CONF_MAIN_BREAKER_CURRENT_A, CONF_MAIN_BREAKER_VOLTAGE_V

# Clés de configuration (réglages + options du configurateur).
CONF_PEAK_ENABLED = "high_load_shed_enabled"
CONF_PEAK_TRIGGER_W = "high_load_trigger_w"
CONF_PEAK_RELEASE_W = "high_load_release_w"
CONF_PEAK_PHASES = "peak_phases"
CONF_PEAK_MEASURE_BASIS = "peak_measure_basis"
CONF_PEAK_TRIGGER_RATIO_PCT = "peak_trigger_ratio_pct"
CONF_PEAK_RELEASE_RATIO_PCT = "peak_release_ratio_pct"
CONF_PEAK_CONFIRM_FRAMES = "peak_confirm_frames"
CONF_PEAK_RELEASE_FRAMES = "peak_release_frames"
CONF_PEAK_SHED_BOILER = "peak_shed_boiler"
CONF_PEAK_SHED_MACHINES = "peak_shed_machines"
CONF_PEAK_RELEASE_INVERTER = "peak_release_inverter"
CONF_PEAK_BLOCK_FLEXIBLE = "peak_block_flexible_starts"
CONF_PEAK_V2H_ASSIST = "peak_v2h_assist"
CONF_PEAK_V2H_TARGET_RATIO_PCT = "peak_v2h_target_ratio_pct"

BASIS_HOUSE = "house"
BASIS_GRID_IMPORT = "grid_import"
MEASURE_BASES = (BASIS_HOUSE, BASIS_GRID_IMPORT)

# Hystérésis minimale garantie entre seuil de déclenchement et de réarmement.
MIN_HYSTERESIS_RATIO = 0.05

EVENT_TRIGGER = "TRIGGER"
EVENT_RELEASE = "RELEASE"

DEFAULTS: dict[str, Any] = {
    CONF_PEAK_PHASES: 1.0,
    CONF_PEAK_MEASURE_BASIS: BASIS_HOUSE,
    CONF_PEAK_TRIGGER_RATIO_PCT: 90.0,
    CONF_PEAK_RELEASE_RATIO_PCT: 0.0,  # 0 = utiliser le seuil absolu de réarmement
    CONF_PEAK_CONFIRM_FRAMES: 0.0,  # 0 = automatique (1 avec disjoncteur, 2 sans)
    CONF_PEAK_RELEASE_FRAMES: 5.0,
    CONF_PEAK_SHED_BOILER: True,
    CONF_PEAK_SHED_MACHINES: True,
    CONF_PEAK_RELEASE_INVERTER: True,
    CONF_PEAK_BLOCK_FLEXIBLE: True,
    CONF_PEAK_V2H_ASSIST: True,
    CONF_PEAK_V2H_TARGET_RATIO_PCT: 80.0,
}


def _number(value: Any, default: float, low: float, high: float) -> float:
    """Convertit en flottant fini borné ; retombe sur ``default`` si invalide."""
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(result):
        return default
    return max(low, min(high, result))


def _flag(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


@dataclass(frozen=True, slots=True)
class PeakShavingConfig:
    """Configuration validée de l'écrêtage de pointe."""

    enabled: bool = False
    breaker_current_a: float = 0.0
    breaker_voltage_v: float = 230.0
    phases: int = 1
    measure_basis: str = BASIS_HOUSE
    trigger_ratio: float = 0.90
    trigger_abs_w: float = 5000.0
    release_ratio: float = 0.0
    release_abs_w: float = 3500.0
    confirm_frames: int = 0
    release_frames: int = 5
    shed_boiler: bool = True
    shed_machines: bool = True
    release_inverter: bool = True
    block_flexible_starts: bool = True
    v2h_assist: bool = True
    v2h_target_ratio: float = 0.80

    @classmethod
    def from_settings(
        cls,
        settings: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
    ) -> "PeakShavingConfig":
        """Construit la configuration ; ``settings`` prime sur ``config``."""
        config = config or {}

        def pick(key: str, default: Any) -> Any:
            if key in settings:
                return settings[key]
            return config.get(key, default)

        basis = str(pick(CONF_PEAK_MEASURE_BASIS, BASIS_HOUSE))
        return cls(
            enabled=pick(CONF_PEAK_ENABLED, False) is True,
            breaker_current_a=_number(pick(CONF_MAIN_BREAKER_CURRENT_A, 0.0) or 0.0, 0.0, 0.0, 1000.0),
            breaker_voltage_v=_number(pick(CONF_MAIN_BREAKER_VOLTAGE_V, 230.0) or 230.0, 230.0, 1.0, 1000.0),
            phases=int(round(_number(pick(CONF_PEAK_PHASES, 1.0), 1.0, 1.0, 3.0))),
            measure_basis=basis if basis in MEASURE_BASES else BASIS_HOUSE,
            trigger_ratio=_number(pick(CONF_PEAK_TRIGGER_RATIO_PCT, 90.0), 90.0, 50.0, 100.0) / 100.0,
            trigger_abs_w=_number(pick(CONF_PEAK_TRIGGER_W, 5000.0), 5000.0, 1.0, 1_000_000.0),
            release_ratio=_number(pick(CONF_PEAK_RELEASE_RATIO_PCT, 0.0), 0.0, 0.0, 99.0) / 100.0,
            release_abs_w=_number(pick(CONF_PEAK_RELEASE_W, 3500.0), 3500.0, 0.0, 1_000_000.0),
            confirm_frames=int(round(_number(pick(CONF_PEAK_CONFIRM_FRAMES, 0.0), 0.0, 0.0, 10.0))),
            release_frames=int(round(_number(pick(CONF_PEAK_RELEASE_FRAMES, 5.0), 5.0, 1.0, 30.0))),
            shed_boiler=_flag(pick(CONF_PEAK_SHED_BOILER, True), True),
            shed_machines=_flag(pick(CONF_PEAK_SHED_MACHINES, True), True),
            release_inverter=_flag(pick(CONF_PEAK_RELEASE_INVERTER, True), True),
            block_flexible_starts=_flag(pick(CONF_PEAK_BLOCK_FLEXIBLE, True), True),
            v2h_assist=_flag(pick(CONF_PEAK_V2H_ASSIST, True), True),
            v2h_target_ratio=_number(pick(CONF_PEAK_V2H_TARGET_RATIO_PCT, 80.0), 80.0, 30.0, 100.0) / 100.0,
        )


def breaker_limit_w(cfg: PeakShavingConfig) -> float | None:
    """Capacité du raccordement en watts (A × V × phases), ``None`` si non renseignée.

    Hypothèse : charge équilibrée entre phases. Une charge concentrée sur une
    seule phase peut dépasser la limite de cette phase sans que le total l'indique.
    """
    if cfg.breaker_current_a <= 0.0 or cfg.breaker_voltage_v <= 0.0:
        return None
    return cfg.breaker_current_a * cfg.breaker_voltage_v * cfg.phases


def trigger_w(cfg: PeakShavingConfig) -> float:
    """Seuil de déclenchement : ratio du disjoncteur, sinon seuil absolu."""
    limit = breaker_limit_w(cfg)
    return limit * cfg.trigger_ratio if limit is not None else cfg.trigger_abs_w


def release_w(cfg: PeakShavingConfig) -> float:
    """Seuil de réarmement, toujours inférieur d'au moins 5 % au déclenchement."""
    limit = breaker_limit_w(cfg)
    trigger = trigger_w(cfg)
    if limit is not None and cfg.release_ratio > 0.0:
        candidate = limit * cfg.release_ratio
    else:
        candidate = cfg.release_abs_w
    return max(0.0, min(candidate, trigger * (1.0 - MIN_HYSTERESIS_RATIO)))


def required_confirm_frames(cfg: PeakShavingConfig) -> int:
    """Trames hautes consécutives requises (auto : 1 avec disjoncteur, 2 sans)."""
    if cfg.confirm_frames > 0:
        return cfg.confirm_frames
    return 1 if breaker_limit_w(cfg) is not None else 2


def measured_power_w(cfg: PeakShavingConfig, *, house_w: float, import_w: float) -> float:
    """Puissance comparée aux seuils : consommation maison ou import réseau."""
    return max(import_w, 0.0) if cfg.measure_basis == BASIS_GRID_IMPORT else house_w


def basis_label(cfg: PeakShavingConfig) -> str:
    return "Import réseau" if cfg.measure_basis == BASIS_GRID_IMPORT else "Puissance maison"


def peak_signal(cfg: PeakShavingConfig, measured_w: float) -> bool:
    """Vrai si la puissance mesurée atteint le seuil de déclenchement."""
    return cfg.enabled and measured_w >= trigger_w(cfg)


@dataclass(frozen=True, slots=True)
class PeakStep:
    """Résultat d'une évaluation : nouveaux compteurs et événement éventuel."""

    high_frames: int
    low_frames: int
    event: str | None
    reason: str
    trigger_w: float
    release_w: float


def evaluate_step(
    cfg: PeakShavingConfig,
    *,
    active: bool,
    measured_w: float,
    high_frames: int,
    low_frames: int,
) -> PeakStep:
    """Machine à états du délestage : déclenche après N trames hautes, réarme après M basses."""
    trigger = trigger_w(cfg)
    release = release_w(cfg)
    label = basis_label(cfg)
    if not active:
        high = high_frames + 1 if measured_w >= trigger else 0
        if high >= required_confirm_frames(cfg):
            return PeakStep(
                0, 0, EVENT_TRIGGER,
                f"{label} {measured_w:.0f} W >= {trigger:.0f} W",
                trigger, release,
            )
        return PeakStep(high, 0, None, "", trigger, release)
    low = low_frames + 1 if measured_w <= release else 0
    if low >= cfg.release_frames:
        return PeakStep(
            0, 0, EVENT_RELEASE,
            f"{cfg.release_frames} trames sous {release:.0f} W",
            trigger, release,
        )
    return PeakStep(0, low, None, "", trigger, release)


def validate(cfg: PeakShavingConfig) -> list[str]:
    """Retourne les codes d'erreur de cohérence (vide si la configuration est saine)."""
    errors: list[str] = []
    if cfg.release_ratio > 0.0 and cfg.release_ratio >= cfg.trigger_ratio:
        errors.append("peak_release_ratio_too_high")
    if breaker_limit_w(cfg) is None and cfg.release_abs_w >= cfg.trigger_abs_w:
        errors.append("peak_release_not_below_trigger")
    if cfg.enabled and breaker_limit_w(cfg) is None and cfg.trigger_abs_w <= 0.0:
        errors.append("peak_trigger_missing")
    return errors
