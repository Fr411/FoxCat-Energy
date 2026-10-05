from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class BoilerThermalEstimate:
    effective_temp_c: float
    confidence_pct: float
    draw_detected: bool
    state: str
    bottom_weight: float
    top_weight: float
    bottom_c: float
    top_c: float | None
    reason: str


class BoilerThermalEstimator:
    """Estimateur robuste pour deux sondes imparfaites.

    - sonde basse/doigt de gant : bonne sécurité mais biaisée pendant/après chauffe ;
    - sonde haute en applique : bonne détection de tendance/puisage mais valeur absolue
      moins fiable.
    Aucune des deux n'est traitée comme vérité absolue pour le fallback.
    """

    def __init__(self) -> None:
        self._last_at: datetime | None = None
        self._last_top: float | None = None
        self._last_bottom: float | None = None
        self._last_heating_at: datetime | None = None

    def update(
        self, *, now: datetime, bottom_c: float, top_c: float | None, boiler_on: bool, settings: dict[str, Any]
    ) -> BoilerThermalEstimate:
        if boiler_on:
            self._last_heating_at = now
        bias_s = max(float(settings.get("boiler_sensor_heat_bias_seconds", 900.0)), 0.0)
        since_heat = (now - self._last_heating_at).total_seconds() if self._last_heating_at else 1e9
        bottom_weight = 0.25 if since_heat < bias_s else 0.55
        top_weight = 1.0 - bottom_weight if top_c is not None else 0.0
        top_offset = float(settings.get("boiler_sensor_top_offset_c", 0.0))
        top_corrected = (float(top_c) + top_offset) if top_c is not None else None
        if top_corrected is None:
            effective = float(bottom_c)
            confidence = 45.0 if since_heat < bias_s else 60.0
            reason = "Sonde haute indisponible : estimation basée sur la sonde basse."
        else:
            effective = float(bottom_c) * bottom_weight + top_corrected * top_weight
            spread = abs(float(bottom_c) - top_corrected)
            confidence = max(30.0, min(90.0, 88.0 - spread * 2.0 - (18.0 if since_heat < bias_s else 0.0)))
            reason = f"Fusion pondérée bas {bottom_weight:.0%} / haut {top_weight:.0%}; écart {spread:.1f} °C."

        drop = float(settings.get("boiler_draw_drop_c", 2.5))
        draw = False
        if top_corrected is not None and self._last_top is not None and self._last_at is not None:
            dt = max((now - self._last_at).total_seconds(), 1.0)
            draw = dt <= 20*60 and (self._last_top - top_corrected) >= drop
        if draw:
            confidence = max(confidence, 70.0)
            state = "PUISAGE_DETECTE"
            reason += " Chute rapide sonde haute : puisage ECS probable."
        elif boiler_on:
            state = "CHAUFFE"
        elif top_corrected is not None and abs(float(bottom_c)-top_corrected) >= 8.0:
            state = "STRATIFIE"
        else:
            state = "STABLE"

        self._last_at = now
        self._last_top = top_corrected
        self._last_bottom = float(bottom_c)
        return BoilerThermalEstimate(
            effective_temp_c=round(effective, 2), confidence_pct=round(confidence, 1),
            draw_detected=draw, state=state, bottom_weight=round(bottom_weight, 3),
            top_weight=round(top_weight, 3), bottom_c=round(float(bottom_c), 2),
            top_c=round(top_corrected, 2) if top_corrected is not None else None, reason=reason,
        )
