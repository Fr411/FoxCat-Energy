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
