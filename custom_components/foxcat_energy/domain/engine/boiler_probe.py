"""Garde de la sonde du boiler : sans mesure de température, aucune chauffe.

Une sonde illisible ne doit jamais être assimilée à 0 °C : FoxCat croirait le ballon froid
et chaufferait sur le réseau, avec une protection contre la surchauffe aveugle. La chauffe est
donc interdite dès que la sonde de régulation disparaît, et rétablie seulement après un retour
stable, pour qu'une sonde instable ne fasse pas osciller la commande.

Module pur : aucune dépendance Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...const import BOILER_BOOST_65, BOILER_HEAT_45

TRANSITION_BLOCKED = "BLOQUE"
TRANSITION_RELEASED = "LIBERE"

# La sonde doit répondre ce temps sans interruption avant de rendre la main.
RECOVER_AFTER_S = 60.0

HEATING_ACTIONS = frozenset({BOILER_HEAT_45, BOILER_BOOST_65})


@dataclass
class BoilerProbeGuard:
    recover_after_s: float = RECOVER_AFTER_S
    blocked: bool = False
    since: datetime | None = None
    _ok_since: datetime | None = field(default=None, repr=False)

    def observe(self, probe_ok: bool, now: datetime) -> str | None:
        """Enregistre l'état de la sonde ; renvoie une transition ou None."""
        if not probe_ok:
            self._ok_since = None
            if not self.blocked:
                self.blocked, self.since = True, now
                return TRANSITION_BLOCKED
            return None
        if not self.blocked:
            return None
        if self._ok_since is None:
            self._ok_since = now
        if (now - self._ok_since).total_seconds() >= self.recover_after_s:
            self.blocked, self.since, self._ok_since = False, None, None
            return TRANSITION_RELEASED
        return None


def is_heating_action(action: str) -> bool:
    return action in HEATING_ACTIONS
