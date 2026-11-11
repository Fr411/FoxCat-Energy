"""Logique pure du décalage de consigne chauffage.

Aucun import Home Assistant : tout est testable unitairement. Le coordinateur
ne fait que lire la configuration et les mesures, appeler :func:`evaluate` et
publier le résultat dans un capteur.

FoxCat n'écrit JAMAIS dans les ``climate.*`` ni dans les ``number.*`` de
Versatile Thermostat : ce module calcule un décalage (°C) selon le surplus
solaire et la présence, et c'est une automatisation Home Assistant qui
l'applique aux presets du thermostat.

L'état (nombre de pas accordés, date du dernier changement) n'est conservé
qu'en mémoire : il repart à 0 au redémarrage, c'est voulu.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

# Clés de réglages (modifiables par entités number / switch).
CONF_HEATING_ENABLED = "heating_boost_enabled"
CONF_HEATING_ONLY_WHEN_EMPTY = "heating_only_when_empty"
CONF_HEATING_MAX_C = "heating_boost_max_c"
CONF_HEATING_STEP_C = "heating_boost_step_c"
CONF_HEATING_SURPLUS_PER_STEP_W = "heating_surplus_per_step_w"
CONF_HEATING_RESERVE_W = "heating_surplus_reserve_w"
CONF_HEATING_HOLD_S = "heating_hold_s"
CONF_HEATING_IMPORT_MAX_W = "heating_import_max_w"
CONF_HEATING_GROUP_LIMIT_W = "heating_group_limit_w"

# Clés de configuration (identifiants d'entités : pas des réglages).
CONF_HEATING_PRESENCE_ENTITY = "heating_presence_entity"
CONF_HEATING_GROUP_POWER_SENSOR = "heating_group_power_sensor"

DEFAULT_PRESENCE_ENTITY = "zone.home"

# Un pas déjà accordé est conservé tant que le surplus reste au moins égal à
# cette fraction de son seuil d'octroi.
HYSTERESIS_RATIO = 0.60
# Pas d'augmentation si la puissance du groupe atteint cette part de la limite.
GROUP_GUARD_RATIO = 0.90

_EPSILON = 1e-9

DEFAULTS: dict[str, Any] = {
    CONF_HEATING_ENABLED: False,
    CONF_HEATING_ONLY_WHEN_EMPTY: True,
    CONF_HEATING_MAX_C: 2.0,
    CONF_HEATING_STEP_C: 0.5,
    CONF_HEATING_SURPLUS_PER_STEP_W: 500.0,
    CONF_HEATING_RESERVE_W: 100.0,
    CONF_HEATING_HOLD_S: 300.0,
    CONF_HEATING_IMPORT_MAX_W: 300.0,
    CONF_HEATING_GROUP_LIMIT_W: 2500.0,
}

_PRESENT_TEXT = {"home", "on", "true"}
_ABSENT_TEXT = {"not_home", "off", "false"}


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


def _optional_number(value: Any) -> float | None:
    """Flottant fini ou ``None`` (mesure absente, inconnue ou invalide)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def parse_presence(state: Any) -> int | None:
    """Convertit l'état d'une entité de présence en nombre de personnes.

    - ``zone.home`` : l'état est déjà un entier (nombre de personnes présentes) ;
    - ``person`` / ``device_tracker`` : ``home`` → 1, ``not_home`` → 0 ;
    - ``binary_sensor`` / ``input_boolean`` : ``on`` → 1, ``off`` → 0.

    Retourne ``None`` si l'état est inconnu, indisponible ou incompréhensible :
    l'appelant doit alors considérer que quelqu'un est présent.
    """
    if state is None or isinstance(state, bool):
        return None
    text = str(state).strip().lower()
    if text in _PRESENT_TEXT:
        return 1
    if text in _ABSENT_TEXT:
        return 0
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return max(int(value), 0)


@dataclass(frozen=True, slots=True)
class HeatingBoostConfig:
    """Configuration validée du décalage de consigne chauffage."""

    enabled: bool = False
    only_when_empty: bool = True
    max_c: float = 2.0
    step_c: float = 0.5
    surplus_per_step_w: float = 500.0
    reserve_w: float = 100.0
    hold_s: float = 300.0
    import_max_w: float = 300.0
    group_limit_w: float = 2500.0
    presence_entity: str = DEFAULT_PRESENCE_ENTITY
    group_power_sensor: str = ""

    @classmethod
    def from_settings(
        cls,
        settings: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
    ) -> "HeatingBoostConfig":
        """Construit la configuration ; ``settings`` prime sur ``config``."""
        config = config or {}

        def pick(key: str, default: Any) -> Any:
            if key in settings:
                return settings[key]
            return config.get(key, default)

        presence = str(pick(CONF_HEATING_PRESENCE_ENTITY, DEFAULT_PRESENCE_ENTITY) or "").strip()
        sensor = str(pick(CONF_HEATING_GROUP_POWER_SENSOR, "") or "").strip()
        return cls(
            enabled=pick(CONF_HEATING_ENABLED, False) is True,
            only_when_empty=_flag(pick(CONF_HEATING_ONLY_WHEN_EMPTY, True), True),
            max_c=_number(pick(CONF_HEATING_MAX_C, 2.0), 2.0, 0.0, 10.0),
            step_c=_number(pick(CONF_HEATING_STEP_C, 0.5), 0.5, 0.1, 5.0),
            surplus_per_step_w=_number(pick(CONF_HEATING_SURPLUS_PER_STEP_W, 500.0), 500.0, 50.0, 20000.0),
            reserve_w=_number(pick(CONF_HEATING_RESERVE_W, 100.0), 100.0, 0.0, 5000.0),
            hold_s=_number(pick(CONF_HEATING_HOLD_S, 300.0), 300.0, 0.0, 3600.0),
            import_max_w=_number(pick(CONF_HEATING_IMPORT_MAX_W, 300.0), 300.0, 0.0, 10000.0),
            group_limit_w=_number(pick(CONF_HEATING_GROUP_LIMIT_W, 2500.0), 2500.0, 100.0, 100000.0),
            presence_entity=presence or DEFAULT_PRESENCE_ENTITY,
            group_power_sensor=sensor,
        )

    @property
    def max_steps(self) -> int:
        """Nombre maximal de pas : ``max_c / step_c`` arrondi à l'entier inférieur."""
        return max(int(math.floor(self.max_c / self.step_c + _EPSILON)), 0)


@dataclass(frozen=True, slots=True)
class HeatingBoostState:
    """État en mémoire : repart à 0 au redémarrage (voulu)."""

    steps: int = 0
    changed_at: float | None = None


@dataclass(frozen=True, slots=True)
class HeatingBoostInputs:
    """Mesures de la trame courante.

    ``presence`` est un nombre de personnes (> 0 : quelqu'un est là) ou
    ``None`` si l'état est inconnu ou indisponible, ce qui vaut « présent ».
    ``group_power_w`` est ``None`` quand le capteur de puissance du groupe de
    climatisation n'est pas configuré ou indisponible.
    """

    regulation_active: bool
    snapshot_valid: bool
    export_w: float
    import_w: float
    presence: int | None = None
    group_power_w: float | None = None


@dataclass(frozen=True, slots=True)
class HeatingBoostResult:
    """Résultat d'une évaluation."""

    offset_c: float
    steps: int
    reason: str
    state: HeatingBoostState
    surplus_w: float | None = None


def _fmt(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _off(reason: str) -> HeatingBoostResult:
    """Retour à 0 : l'état est remis à zéro."""
    return HeatingBoostResult(0.0, 0, reason, HeatingBoostState())


# FONCTION : evaluate — Calcule le décalage de consigne chauffage
def evaluate(
    cfg: HeatingBoostConfig,
    state: HeatingBoostState,
    inputs: HeatingBoostInputs,
    now_ts: float,
) -> HeatingBoostResult:
    """Retourne le décalage (°C), le nombre de pas, la raison et le nouvel état.

    Règles, dans l'ordre :

    1. Retour à 0 si la fonction est désactivée, si la régulation FoxCat est
       inactive, si le snapshot est invalide, ou si « uniquement maison vide »
       est actif alors que quelqu'un est présent (présence inconnue = présent).
    2. Surplus = export + puissance du groupe de clim − marge de réserve : le
       chauffage consomme déjà une partie du surplus qu'il utilise.
    3. Pas = ``floor(surplus / surplus_par_pas)``, borné à ``max_c / pas_c``.
    4. Hystérésis : un pas déjà accordé est conservé tant que le surplus reste
       au moins égal à 60 % de son seuil.
    5. Anti-yoyo : toute augmentation attend ``hold_s`` après le dernier
       changement. Une baisse est immédiate si l'import dépasse ``import_max_w``,
       sinon elle respecte l'hystérésis.
    6. Garde de puissance : pas d'augmentation si la puissance du groupe atteint
       90 % de la limite du groupe.
    """
    # 1) Conditions d'arrêt.
    if not cfg.enabled:
        return _off("Fonction désactivée.")
    if not inputs.regulation_active:
        return _off("Régulation FoxCat inactive : aucun décalage.")
    if not inputs.snapshot_valid:
        return _off("Mesures énergétiques invalides : aucun décalage.")
    if cfg.only_when_empty and (inputs.presence is None or inputs.presence > 0):
        if inputs.presence is None:
            return _off("Présence inconnue (considérée présente) : aucun décalage.")
        return _off("Maison occupée : aucun décalage (réglage « uniquement maison vide »).")

    export_w = max(_optional_number(inputs.export_w) or 0.0, 0.0)
    import_w = max(_optional_number(inputs.import_w) or 0.0, 0.0)
    group_w = _optional_number(inputs.group_power_w)
    group_w = max(group_w, 0.0) if group_w is not None else None

    # 2) Surplus disponible : le chauffage déjà en cours fait partie du surplus.
    surplus = export_w + (group_w or 0.0) - cfg.reserve_w

    # 3) Nombre de pas accordés par le surplus, borné au maximum.
    max_steps = cfg.max_steps
    desired = min(int(math.floor(max(surplus, 0.0) / cfg.surplus_per_step_w + _EPSILON)), max_steps)

    current = min(max(int(state.steps), 0), max_steps)
    elapsed = None if state.changed_at is None else now_ts - state.changed_at

    # 4) Hystérésis : conserver le pas tant que surplus >= 60 % de son seuil.
    hold_steps = min(
        current,
        int(math.floor(max(surplus, 0.0) / (cfg.surplus_per_step_w * HYSTERESIS_RATIO) + _EPSILON)),
    )

    target = current
    why = ""
    if desired > current:
        # 5) Anti-yoyo et 6) garde de puissance : seules les augmentations sont freinées.
        if elapsed is not None and elapsed < cfg.hold_s:
            why = f"augmentation retenue ({max(cfg.hold_s - elapsed, 0.0):.0f} s d'attente)"
        elif group_w is not None and group_w >= GROUP_GUARD_RATIO * cfg.group_limit_w:
            why = (
                f"augmentation bloquée : groupe à {group_w:.0f} W "
                f"(≥ {GROUP_GUARD_RATIO * 100:.0f} % de {cfg.group_limit_w:.0f} W)"
            )
        else:
            target = desired
            why = "augmentation"
    elif import_w > cfg.import_max_w:
        target = desired
        why = f"baisse immédiate : import {import_w:.0f} W > {cfg.import_max_w:.0f} W"
    else:
        target = max(desired, hold_steps)
        if target < current:
            why = f"baisse : surplus sous {HYSTERESIS_RATIO * 100:.0f} % du seuil du pas"
        elif current > desired:
            why = "maintien (hystérésis)"
        else:
            why = "stable"

    changed_at = state.changed_at
    if target != current:
        changed_at = now_ts
    new_state = HeatingBoostState(steps=target, changed_at=changed_at)
    offset = round(target * cfg.step_c, 4)
    reason = (
        f"Décalage {_fmt(offset)} °C ({target}/{max_steps} pas) : "
        f"surplus {surplus:.0f} W, {why}."
    )
    if target != current:
        reason = (
            f"Décalage {_fmt(offset)} °C ({target}/{max_steps} pas), "
            f"précédent {_fmt(current * cfg.step_c)} °C : surplus {surplus:.0f} W, {why}."
        )
    return HeatingBoostResult(offset, target, reason, new_state, surplus)
