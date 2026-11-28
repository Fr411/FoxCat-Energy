import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "rt_rules", Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy" / "domain" / "engine" / "runtime_rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)


def test_socket_should_be_on():
    assert rules.socket_should_be_on(management=True, cycle_active=False, allowed=True, allow_start_now=True)
    assert not rules.socket_should_be_on(management=True, cycle_active=False, allowed=True, allow_start_now=False)
    assert not rules.socket_should_be_on(management=False, cycle_active=False, allowed=True, allow_start_now=True)
    assert rules.socket_should_be_on(management=False, cycle_active=True, allowed=False, allow_start_now=False)


def test_socket_sync_status():
    assert rules.socket_sync_status(True, "on") == "OK"
    assert rules.socket_sync_status(False, "on") == "ECART"
    assert rules.socket_sync_status(True, "unavailable") == "INDISPONIBLE"
    assert rules.socket_sync_status(False, None) == "INDISPONIBLE"


def test_socket_sync_signature_changes_on_plan_edge():
    base = [{"id": "w", "switch": "switch.w", "tariff_start_favorable": False, "window_open": True, "automatic": True}]
    later = [{**base[0], "tariff_start_favorable": True}]
    assert rules.socket_sync_signature(base) != rules.socket_sync_signature(later)
    assert rules.socket_sync_signature([{**base[0], "switch": None}]) == {}


_spec2 = importlib.util.spec_from_file_location(
    "rt_mode", Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy" / "domain" / "loads" / "machine_mode.py")
mm = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(mm)

from datetime import datetime, timedelta, timezone  # noqa: E402

_NOW = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)
_ARGS = dict(management=False, keep_running=False, backup_on=False, high_load_block=False, allowed=True, tariff_ok=True)


def test_mode_arret_coupe_la_prise_sauf_cycle():
    assert rules.machine_socket_action(cycle_active=False, stopped=True, **_ARGS) == "turn_off"
    assert rules.machine_socket_action(cycle_active=True, stopped=True, **_ARGS) is None
    # Manuel : FoxCat ne commande rien.
    assert rules.machine_socket_action(cycle_active=False, stopped=False, **_ARGS) is None


def test_mode_arret_prioritaire_sur_backup():
    args = {**_ARGS, "backup_on": True}
    assert rules.machine_socket_action(cycle_active=False, stopped=True, **args) == "turn_off"


def test_manuel_expire_apres_24h():
    since = (_NOW - timedelta(hours=23, minutes=59)).isoformat()
    assert not mm.manual_expired(mm.MACHINE_MODE_MANUAL, since, _NOW)
    since = (_NOW - timedelta(hours=24)).isoformat()
    assert mm.manual_expired(mm.MACHINE_MODE_MANUAL, since, _NOW)
    assert mm.manual_expired(mm.MACHINE_MODE_MANUAL, None, _NOW)
    assert not mm.manual_expired(mm.MACHINE_MODE_OFF, since, _NOW)
    assert not mm.manual_expired(mm.MACHINE_MODE_AUTO, since, _NOW)


def test_mode_suit_le_booleen_historique():
    assert mm.reconcile_mode(mm.MACHINE_MODE_OFF, True) == mm.MACHINE_MODE_AUTO
    assert mm.reconcile_mode(mm.MACHINE_MODE_OFF, False) == mm.MACHINE_MODE_OFF
    assert mm.reconcile_mode(mm.MACHINE_MODE_MANUAL, False) == mm.MACHINE_MODE_MANUAL
    assert mm.reconcile_mode(mm.MACHINE_MODE_AUTO, False) == mm.MACHINE_MODE_MANUAL
    assert mm.reconcile_mode(None, False) == mm.MACHINE_MODE_MANUAL


def test_retour_automatique_prevu():
    assert mm.manual_until("2026-11-28T12:00:00+00:00") == "2026-11-29T12:00:00+00:00"
    assert mm.manual_until("n/a") is None
