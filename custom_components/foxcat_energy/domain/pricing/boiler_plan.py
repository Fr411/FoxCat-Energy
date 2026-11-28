"""Démarrage prévu du boiler en heures creuses (bi-horaire), pour la vue du planificateur.

Logique pure, qui **reproduit** la règle réelle du boiler (``domain/engine/modes/eco.py`` et
``common.ecs_last_departure``) sans la remplacer :

* en heures creuses, la chauffe réseau n'est autorisée que si l'eau est sous le seuil de démarrage
  (``boiler_temp_start_c``, 43 °C) ;
* avec l'option « attendre le dernier failback » (active par défaut), elle ne démarre qu'au **dernier
  moment** qui permet encore d'atteindre la température normale (45 °C) avant la fin des heures creuses,
  moins la marge de sécurité, pour laisser sa chance au solaire ;
* le solaire peut toujours chauffer plus tôt : l'heure rendue est donc « au plus tard ».

L'eau est supposée refroidir à ``boiler_cool_rate_c_per_h`` tant qu'on ne chauffe pas.
"""
from __future__ import annotations

from typing import Any

from ..engine.modes.common import cool_rate_c_per_h, heat_rate_c_per_h

HORIZON_S = 36 * 3600


def _num(settings: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(settings.get(key, default))
    except (TypeError, ValueError):
        return default


def _heating_minutes(temp_at_end_c: float, normal_c: float, heat_rate: float) -> float:
    return max(0.0, (normal_c - temp_at_end_c) / heat_rate * 60.0)


def plan_boiler_hc(
    *,
    now_ts: int,
    settings: dict[str, Any],
    temp_c: float | None,
    boiler_on: bool,
    hc_windows: list[tuple[int, int]],
    mode: str | None = None,
) -> dict[str, Any]:
    """Statut et heure de démarrage prévue du boiler sur les heures creuses."""
    start_c = _num(settings, "boiler_temp_start_c", 43.0)
    normal_c = _num(settings, "boiler_temp_normal_c", 45.0)
    margin_s = max(_num(settings, "boiler_failback_margin_min", 30.0), 0.0) * 60.0
    heat = heat_rate_c_per_h(settings)
    cool = cool_rate_c_per_h(settings)
    wait_failback = bool(settings.get("boiler_hc_wait_failback", True))
    base = {
        "start_ts": None, "end_ts": None, "heating_min": None, "temp_c": temp_c,
        "start_temp_c": start_c, "target_c": normal_c,
        "window_start_ts": None, "window_end_ts": None, "failback": wait_failback,
    }

    if mode == "Manuel":
        return base | {"status": "MANUEL", "reason": "Mode Manuel : FoxCat ne commande pas le boiler."}
    if not settings.get("boiler_enabled", True):
        return base | {"status": "DESACTIVE", "reason": "Boiler non géré par FoxCat."}
    if temp_c is None:
        return base | {"status": "SONDE_INDISPONIBLE", "reason": "Température du boiler illisible : aucune chauffe prévue."}
    if not settings.get("boiler_allow_hc", True):
        return base | {"status": "HC_DESACTIVE", "reason": "Chauffe réseau en heures creuses désactivée : solaire seulement."}

    if boiler_on and temp_c < normal_c:
        minutes = _heating_minutes(temp_c, normal_c, heat) if heat else 0.0
        return base | {
            "status": "EN_COURS", "start_ts": now_ts, "end_ts": int(now_ts + minutes * 60), "heating_min": round(minutes),
            "reason": f"Chauffe en cours : {temp_c:.1f} °C vers {normal_c:.1f} °C.",
        }

    # Instant où l'eau passe sous le seuil de démarrage (si elle refroidit).
    if temp_c < start_c:
        cross = now_ts
    elif cool > 0:
        cross = now_ts + int((temp_c - start_c) / cool * 3600)
    else:
        cross = None
    if cross is None or cross > now_ts + HORIZON_S:
        return base | {
            "status": "AUCUN_BESOIN",
            "reason": f"Eau à {temp_c:.1f} °C, au-dessus du seuil de démarrage ({start_c:.0f} °C) : pas de chauffe réseau prévue.",
        }

    def temp_at(t: int) -> float:
        return temp_c - cool * max(t - now_ts, 0) / 3600.0

    for ws, we in sorted(hc_windows):
        if we <= now_ts or we <= cross:
            continue
        t_in = max(ws, now_ts, cross)
        if not wait_failback:
            start = t_in
        else:
            start = None
            t = t_in
            while t <= we:
                projected_end = temp_at(t) - cool * (we - t) / 3600.0
                minutes = _heating_minutes(projected_end, normal_c, heat)
                if we - t - minutes * 60.0 - margin_s <= 0:
                    start = t
                    break
                t += 60
            if start is None:
                start = we
        minutes = _heating_minutes(temp_at(start), normal_c, heat)
        end = min(int(start + minutes * 60), we)
        immediate = start <= now_ts + 60
        return base | {
            "status": "MAINTENANT" if immediate else "PROGRAMME",
            "start_ts": int(start), "end_ts": int(end), "heating_min": round(minutes),
            "window_start_ts": int(ws), "window_end_ts": int(we),
            "reason": (
                f"Chauffe réseau {'immédiate' if immediate else 'au plus tard à l’heure indiquée'} : "
                f"{temp_at(start):.1f} → {normal_c:.1f} °C en {round(minutes)} min "
                f"(fin des heures creuses, marge {round(margin_s / 60)} min). Le solaire peut chauffer avant."
            ),
        }
    return base | {"status": "AUCUNE_HC", "reason": "Aucune heure creuse exploitable sur l'horizon."}
