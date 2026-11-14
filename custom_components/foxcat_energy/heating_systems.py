"""Systèmes de chauffage (pompes à chaleur) : modèle de données et validation.

Aucun import Home Assistant : tout est testable unitairement.

Un système = un groupe extérieur de pompe à chaleur, avec :
- un capteur de puissance (obligatoire) ;
- un capteur de tension (optionnel) ;
- la phase du réseau sur laquelle il est raccordé (optionnelle) ;
- uniquement pour une PAC air/air : de 0 à 5 unités intérieures (``climate.*``).
  Les PAC eau/eau et air/eau n'ont pas d'unités intérieures à lier.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

# Clé de stockage dans les options de l'entrée de configuration.
CONF_HEATING_SYSTEMS = "heating_systems_v1"

TYPE_AIR_AIR = "air_air"
TYPE_WATER_WATER = "water_water"
TYPE_AIR_WATER = "air_water"
SYSTEM_TYPES = (TYPE_AIR_AIR, TYPE_WATER_WATER, TYPE_AIR_WATER)
SYSTEM_TYPE_LABELS = {
    TYPE_AIR_AIR: "Pompe à chaleur air/air",
    TYPE_WATER_WATER: "Pompe à chaleur eau/eau",
    TYPE_AIR_WATER: "Pompe à chaleur air/eau",
}

PHASES = ("L1", "L2", "L3")
# Température de consigne maximale écrite par FoxCat sur les unités d'un système.
DEFAULT_MAX_SETPOINT_C = 24.0
MIN_MAX_SETPOINT_C = 16.0
MAX_MAX_SETPOINT_C = 30.0
# Un groupe air/air peut desservir au plus ce nombre d'unités intérieures.
MAX_INDOOR_UNITS = 5

ERR_INVALID = "invalid_heating_system"
ERR_TOO_MANY_UNITS = "heating_too_many_indoor_units"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bounded(value: Any, default: float, low: float, high: float) -> float:
    """Flottant fini borné ; ``default`` si la valeur est absente ou invalide."""
    if value is None or isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return round(max(low, min(high, result)), 2) if math.isfinite(result) else default


def indoor_units_from(value: Any) -> list[str]:
    """Liste d'identifiants ``climate.*`` sans vides ni doublons, ordre conservé."""
    if value is None:
        return []
    items: Iterable[Any] = [value] if isinstance(value, str) else value
    seen: list[str] = []
    for item in items:
        entity_id = _text(item)
        if entity_id and entity_id not in seen:
            seen.append(entity_id)
    return seen


def normalise_system(user_input: dict[str, Any], system_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Valide une saisie et retourne ``(enregistrement, None)`` ou ``(None, code_erreur)``."""
    name = _text(user_input.get("name"))
    system_type = _text(user_input.get("system_type")).lower()
    power_sensor = _text(user_input.get("power_sensor"))
    if not name or system_type not in SYSTEM_TYPES or not power_sensor:
        return None, ERR_INVALID

    phase = _text(user_input.get("phase")).upper()
    if phase not in PHASES:
        phase = ""

    units: list[str] = []
    if system_type == TYPE_AIR_AIR:
        units = indoor_units_from(user_input.get("indoor_units"))
        if len(units) > MAX_INDOOR_UNITS:
            return None, ERR_TOO_MANY_UNITS

    return {
        "id": system_id,
        "name": name,
        "system_type": system_type,
        "power_sensor": power_sensor,
        "voltage_sensor": _text(user_input.get("voltage_sensor")),
        "phase": phase,
        "indoor_units": units,
        # Air/air seulement : FoxCat règle lui-même la consigne des unités intérieures.
        "max_setpoint_c": _bounded(
            user_input.get("max_setpoint_c"), DEFAULT_MAX_SETPOINT_C, MIN_MAX_SETPOINT_C, MAX_MAX_SETPOINT_C
        ),
        "apply_setpoint": system_type == TYPE_AIR_AIR and bool(units) and user_input.get("apply_setpoint") is True,
    }, None


def records_from(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Enregistrements valides stockés dans les options (les autres sont ignorés)."""
    raw = options.get(CONF_HEATING_SYSTEMS)
    if not isinstance(raw, list):
        return []
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not _text(item.get("id")):
            continue
        record, _error = normalise_system(item, _text(item.get("id")))
        if record is not None:
            records.append(record)
    return records


def summary(record: dict[str, Any]) -> str:
    """Libellé court pour les menus : « Salon — PAC air/air (3 unités) »."""
    label = SYSTEM_TYPE_LABELS.get(record.get("system_type"), "PAC")
    units = len(record.get("indoor_units") or [])
    extra = f" ({units} unité{'s' if units > 1 else ''})" if record.get("system_type") == TYPE_AIR_AIR and units else ""
    return f"{record.get('name')} — {label}{extra}"


# --- Optimisation des consignes des unités intérieures (air/air) ---
#
# Pour chaque système dont « FoxCat applique la consigne » est actif :
# - avant toute modification, l'état (mode) et la consigne de l'unité sont mémorisés ;
# - tant qu'un décalage est accordé (donc seulement si le décalage de consigne est
#   activé), les unités en chauffage reçoivent la même consigne (moyenne des
#   consignes d'origine + décalage, plafonnée par la température max du système,
#   sans jamais baisser une unité) et les unités éteintes sont allumées au même
#   niveau, même si toutes sont éteintes ;
# - dès que l'optimisation n'est plus possible, l'état et la consigne mémorisés sont rétablis.

HEAT_MODE = "heat"
OFF_MODE = "off"
# Écart (°C) en dessous duquel deux consignes sont considérées identiques.
SETPOINT_TOLERANCE_C = 0.05
# Écart toléré entre la consigne lue et la dernière consigne écrite (arrondis de l'unité) :
# au-delà, c'est une modification manuelle.
USER_CHANGE_TOLERANCE_C = 0.25
DEFAULT_STEP_C = 0.5
_EPSILON = 1e-9


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def clean_track(raw: Any) -> dict[str, Any] | None:
    """Valide un suivi relu du stockage ; ``None`` s'il est inutilisable.

    Un suivi contient ``mode`` (mode avant optimisation), ``base`` (consigne avant
    optimisation, absente si l'unité n'en avait pas) et ``target`` (dernière consigne
    écrite), ou seulement ``suppressed`` quand l'utilisateur a éteint une unité
    que FoxCat avait allumée.
    """
    if not isinstance(raw, dict):
        return None
    if raw.get("suppressed") is True:
        return {"suppressed": True}
    mode = _text(raw.get("mode")).lower()
    target = _finite(raw.get("target"))
    if mode not in (HEAT_MODE, OFF_MODE) or target is None:
        return None
    track: dict[str, Any] = {"mode": mode, "target": round(target, 2)}
    base = _finite(raw.get("base"))
    if base is not None:
        track["base"] = round(base, 2)
    return track


@dataclass(frozen=True, slots=True)
class UnitState:
    """Lecture d'une unité intérieure (entité ``climate``)."""

    entity_id: str
    mode: str                        # état de l'entité : « heat », « off », « cool »…
    setpoint_c: float | None = None  # attribut ``temperature``
    min_c: float | None = None
    max_c: float | None = None
    step_c: float | None = None
    can_heat: bool = True            # « heat » figure dans les modes de l'unité


@dataclass(frozen=True, slots=True)
class UnitAction:
    """Appels à faire sur une unité, dans cet ordre : mode, consigne, mode."""

    entity_id: str
    pre_mode: str | None = None
    set_to: float | None = None
    post_mode: str | None = None


@dataclass(frozen=True, slots=True)
class SystemPlan:
    """Actions à faire et nouveaux suivis (``None`` = suivi à supprimer), par unité."""

    actions: list[UnitAction]
    tracks: dict[str, dict[str, Any] | None]


def _snap(value: float, step: float, ceiling: float | None, floor_value: float | None) -> float:
    """Arrondit au pas de l'unité (arrondi classique) sans dépasser ``ceiling``."""
    snapped = math.floor(value / step + 0.5 + _EPSILON) * step
    if ceiling is not None and snapped > ceiling + _EPSILON:
        snapped = math.floor(ceiling / step + _EPSILON) * step
    if floor_value is not None:
        snapped = max(snapped, floor_value)
    return snapped


def plan_system(
    tracks: dict[str, dict[str, Any]],
    units: list[UnitState],
    *,
    offset_c: Any,
    max_setpoint_c: Any = DEFAULT_MAX_SETPOINT_C,
) -> SystemPlan:
    """Planifie l'optimisation des consignes d'un système (voir l'en-tête de section).

    ``tracks`` : suivis courants par ``entity_id``. ``units`` : unités disponibles
    (les indisponibles sont omises par l'appelant, leur suivi est conservé).
    """
    offset = max(_finite(offset_c) or 0.0, 0.0)
    cap = _finite(max_setpoint_c)
    actions: list[UnitAction] = []
    new_tracks: dict[str, dict[str, Any] | None] = {}

    # 1) Suivi courant de chaque unité, corrigé des interventions manuelles.
    live: dict[str, dict[str, Any] | None] = {}
    for unit in units:
        track = clean_track(tracks.get(unit.entity_id))
        mode = _text(unit.mode).lower()
        setpoint = _finite(unit.setpoint_c)
        if track is not None and not track.get("suppressed"):
            if track["mode"] == OFF_MODE:
                if mode != HEAT_MODE:
                    # L'utilisateur a éteint une unité que FoxCat avait allumée : ne plus y toucher.
                    track = {"suppressed": True} if offset > 0 else None
                elif setpoint is not None and abs(setpoint - track["target"]) > USER_CHANGE_TOLERANCE_C:
                    track = {"mode": HEAT_MODE, "base": round(setpoint, 2), "target": round(setpoint, 2)}
            elif mode != HEAT_MODE:
                # Éteinte ou changée de mode à la main pendant la rehausse : on ne la rallume pas.
                track = {"suppressed": True} if offset > 0 else None
            elif setpoint is not None and abs(setpoint - track["target"]) > USER_CHANGE_TOLERANCE_C:
                track = {"mode": HEAT_MODE, "base": round(setpoint, 2), "target": round(setpoint, 2)}
        elif track is not None and offset <= 0:
            track = None  # fin de la rehausse : on peut de nouveau agir sur cette unité
        live[unit.entity_id] = track

    def own(unit: UnitState) -> dict[str, Any] | None:
        track = live[unit.entity_id]
        return track if track and not track.get("suppressed") else None

    heating = [u for u in units if _text(u.mode).lower() == HEAT_MODE and _finite(u.setpoint_c) is not None]
    # Unités de référence : celles que l'utilisateur chauffe lui-même.
    anchors = [u for u in heating if not (own(u) and own(u)["mode"] == OFF_MODE)]
    bases: list[float] = [(own(u) or {}).get("base", _finite(u.setpoint_c)) for u in anchors]
    if not bases:
        # Tout est éteint : le décalage activé suffit à allumer les unités. Leur consigne
        # d'avant optimisation (ou, à défaut, celle qu'elles affichent) sert de référence.
        for unit in units:
            track = own(unit)
            setpoint = _finite(unit.setpoint_c)
            if track is not None and track["mode"] == OFF_MODE and "base" in track:
                bases.append(track["base"])
            elif (
                track is None and _text(unit.mode).lower() == OFF_MODE and unit.can_heat
                and not (live[unit.entity_id] or {}).get("suppressed") and setpoint is not None
            ):
                bases.append(setpoint)

    if offset <= 0 or not bases:
        # 2) Optimisation impossible : rétablir le mode et la consigne mémorisés.
        for unit in units:
            track = own(unit)
            mode = _text(unit.mode).lower()
            if track is not None and mode == HEAT_MODE:
                setpoint = _finite(unit.setpoint_c)
                base = track.get("base")
                restore = base if base is not None and (
                    setpoint is None or abs(base - setpoint) > SETPOINT_TOLERANCE_C
                ) else None
                post = OFF_MODE if track["mode"] == OFF_MODE else None
                if restore is not None or post is not None:
                    actions.append(UnitAction(unit.entity_id, set_to=restore, post_mode=post))
            if tracks.get(unit.entity_id) is not None:
                new_tracks[unit.entity_id] = None
        return SystemPlan(actions, new_tracks)

    # 3) Consigne commune : moyenne des consignes d'origine des unités de référence + décalage.
    mean_base = sum(bases) / len(bases)
    common = mean_base + offset
    if cap is not None:
        common = min(common, cap)

    def desired_for(unit: UnitState, floor_value: float | None) -> float:
        step = _finite(unit.step_c)
        step = step if step and step > 0 else DEFAULT_STEP_C
        # Jamais en dessous de la consigne d'origine : l'optimisation ne fait que monter.
        value = _snap(common, step, cap, floor_value)
        low, high = _finite(unit.min_c), _finite(unit.max_c)
        if low is not None:
            value = max(value, low)
        if high is not None:
            value = min(value, high)
        return round(value, 2)

    for unit in units:
        track = own(unit)
        mode = _text(unit.mode).lower()
        setpoint = _finite(unit.setpoint_c)
        suppressed = bool((live[unit.entity_id] or {}).get("suppressed"))
        if mode == HEAT_MODE and setpoint is not None:
            turned_on = track is not None and track["mode"] == OFF_MODE
            base = track["base"] if track and "base" in track else setpoint
            # Une unité allumée par FoxCat n'a pas de consigne à ne pas baisser : seule la consigne commune compte.
            target = desired_for(unit, None if turned_on else base)
            write = None if abs(target - setpoint) <= SETPOINT_TOLERANCE_C else target
            if write is not None:
                actions.append(UnitAction(unit.entity_id, set_to=write))
            if turned_on:
                new_tracks[unit.entity_id] = {**track, "target": target}
            elif abs(target - base) <= SETPOINT_TOLERANCE_C and track is None:
                new_tracks[unit.entity_id] = None
            else:
                new_tracks[unit.entity_id] = {"mode": HEAT_MODE, "base": base, "target": target}
        elif mode == OFF_MODE and unit.can_heat and not suppressed:
            # Unité éteinte : on la rallume à la consigne commune, en mémorisant son état d'origine.
            target = desired_for(unit, None)
            actions.append(UnitAction(unit.entity_id, pre_mode=HEAT_MODE, set_to=target))
            new_track: dict[str, Any] = {"mode": OFF_MODE, "target": target}
            if setpoint is not None:
                new_track["base"] = round(setpoint, 2)
            new_tracks[unit.entity_id] = new_track
        elif live[unit.entity_id] != tracks.get(unit.entity_id):
            new_tracks[unit.entity_id] = live[unit.entity_id]
    return SystemPlan(actions, new_tracks)
