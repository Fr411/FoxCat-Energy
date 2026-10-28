import importlib.util
import math
import sys
from pathlib import Path

path = Path(__file__).parents[1] / "custom_components" / "foxcat_energy" / "grid_load.py"
spec = importlib.util.spec_from_file_location("grid_load_under_test", path)
gl = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gl
spec.loader.exec_module(gl)


def test_mono_current_and_percentage():
    r = gl.evaluate("MONO", power_w=6900, voltage_v=230, cos_phi=1.0, breaker_a=40, limit_pct=85)
    assert math.isclose(r.current_a, 30.0)
    assert math.isclose(r.load_pct, 75.0)
    assert not r.exceeded and r.discharge_w == 0.0


def test_mono_excess_converted_to_watts():
    r = gl.evaluate("MONO", power_w=9200, voltage_v=230, cos_phi=1.0, breaker_a=40, limit_pct=85)
    assert math.isclose(r.excess_a, 6.0)
    assert math.isclose(r.discharge_w, 6.0 * 230)
    assert r.exceeded


def test_tri_uses_phase_measurements_first():
    r = gl.evaluate("TRI", power_w=1000, voltage_v=230, cos_phi=1.0, breaker_a=32, limit_pct=85,
                    phase_currents_a=[10.0, 30.0, None])
    assert r.source == "phases" and r.current_a == 30.0


def test_tri_fallback_power_formula():
    r = gl.evaluate("TETRA", power_w=20000, voltage_v=400, cos_phi=0.95, breaker_a=40, limit_pct=85)
    assert r.source == "power"
    assert math.isclose(r.current_a, 20000 / (math.sqrt(3) * 400 * 0.95))


def test_disabled_or_no_breaker_never_discharges():
    assert gl.evaluate("MONO", power_w=9999, voltage_v=230, cos_phi=1, breaker_a=40, limit_pct=85, enabled=False).discharge_w == 0
    assert gl.evaluate("MONO", power_w=9999, voltage_v=230, cos_phi=1, breaker_a=0, limit_pct=85).load_pct is None
