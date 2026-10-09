from __future__ import annotations

from .models import EnergySnapshot


def boiler_surplus_before_load_w(snapshot: EnergySnapshot) -> float:
    """Return the network surplus available before the boiler load.

    ``grid_net_w`` is positive on export and negative on import. When the boiler
    is already ON, its measured power is added back so a protected machine does
    not automatically force the boiler OFF merely because the boiler itself has
    consumed the export.
    """
    available = snapshot.grid_net_w
    if snapshot.boiler_on:
        available += max(snapshot.boiler_power_w, 0.0)
    return max(available, 0.0)


def protected_cycle_boiler_allowed(
    snapshot: EnergySnapshot,
    settings: dict[str, object],
    *,
    margin_w: float = 0.0,
) -> bool:
    """Allow boiler during a protected appliance cycle only on real surplus.

    A protected cycle keeps priority, but no longer forbids the boiler by
    itself. The boiler may run when the measured PV surplus remaining after the
    protected appliance is sufficient to cover the configured boiler power.
    """
    if not snapshot.machine_active:
        return True
    required = max(float(settings.get("boiler_power_w", 0.0)) + margin_w, 0.0)
    return boiler_surplus_before_load_w(snapshot) >= required


def protected_cycle_boiler_allowed_stable(
    snapshot: EnergySnapshot,
    t0: EnergySnapshot,
    settings: dict[str, object],
) -> bool:
    """Two-frame guard used before starting/maintaining the boiler.

    If a protected cycle has just started between T0 and NOW, wait for a fresh
    acquisition instead of authorising the boiler from a pre-machine sample.
    """
    if not snapshot.machine_active:
        return True
    if not t0.machine_active:
        return False
    return protected_cycle_boiler_allowed(snapshot, settings) and protected_cycle_boiler_allowed(t0, settings)
