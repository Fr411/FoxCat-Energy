"""Hooks Home Assistant en lecture seule.

Aucun import de Home Assistant au niveau module et aucun appel de service : le module ne
fait que lire ``hass.states`` pour des capteurs de mesure. Il n'est branché nulle part
automatiquement (désactivé par défaut) ; un appelant explicite doit l'instancier.
"""
from __future__ import annotations

from typing import Any, Mapping

from .config import VirtualAssetsConfig, config_from_settings
from .diagnostics import build_diagnostics
from .shadow import ShadowSimulator


def read_float_state(hass: Any, entity_id: str | None) -> float | None:
    """Lit un capteur ; ``None`` si absent, ``unknown``/``unavailable`` ou non numérique."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


class VirtualAssetsRuntime:
    """Conteneur d'exécution ; ``shadow`` vaut ``None`` tant que le module est désactivé."""

    def __init__(self, config: VirtualAssetsConfig) -> None:
        self.config = config
        self.shadow: ShadowSimulator | None = \
            ShadowSimulator(config) if config.enabled and config.shadow_mode else None

    def diagnostics(self) -> dict[str, Any]:
        return build_diagnostics(self.config, None if self.shadow is None
                                 else self.shadow.snapshot())

    def unload(self) -> None:
        self.shadow = None


def setup_virtual_assets(settings: Mapping[str, Any] | None) -> VirtualAssetsRuntime:
    return VirtualAssetsRuntime(config_from_settings(settings))
