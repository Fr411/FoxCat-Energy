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


def test_voltages_phase_and_line_are_cross_checked():
    v = gl.resolve_voltages(230, phase_v=[231, 229, 230], line_v=[399, 400, 401])
    assert v.source == gl.VOLTAGE_BOTH
    assert math.isclose(v.phase_v, (230 + 400 / math.sqrt(3)) / 2)
    assert math.isclose(v.spread_pct, 2 / 230 * 100)


def test_voltages_derived_from_line_only():
    v = gl.resolve_voltages(230, line_v=[400, 400, 400])
    assert v.source == gl.VOLTAGE_LINE and math.isclose(v.phase_v, 400 / math.sqrt(3))


def test_voltages_ignore_aberrant_values_and_fall_back_to_nominal():
    v = gl.resolve_voltages(230, phase_v=[0, None, 9999], line_v=[None])
    assert v.source == gl.VOLTAGE_NOMINAL and v.phase_v == 230


def test_voltages_nominal_400_is_converted_to_phase_voltage():
    assert math.isclose(gl.resolve_voltages(400).phase_v, 400 / math.sqrt(3))


def test_imbalance_factor_raises_estimated_current_without_phase_sensors():
    base = gl.evaluate("TRI", power_w=12000, voltage_v=230, cos_phi=1.0, breaker_a=25, limit_pct=90)
    worst = gl.evaluate("TRI", power_w=12000, voltage_v=230, cos_phi=1.0, breaker_a=25, limit_pct=90,
                        imbalance_factor=1.5)
    assert math.isclose(worst.current_a, base.current_a * 1.5)
    assert worst.source == "power"


def test_imbalance_factor_ignored_with_measured_phases_and_in_mono():
    r = gl.evaluate("TRI", power_w=1000, voltage_v=230, cos_phi=1.0, breaker_a=32, limit_pct=85,
                    phase_currents_a=[10.0, 30.0, 5.0], imbalance_factor=2.0)
    assert r.current_a == 30.0
    m = gl.evaluate("MONO", power_w=2300, voltage_v=230, cos_phi=1.0, breaker_a=40, limit_pct=85,
                    imbalance_factor=2.0)
    assert math.isclose(m.current_a, 10.0)


def test_imbalance_factor_is_clamped():
    assert gl.clamp_imbalance_factor(0.5) == 1.0
    assert gl.clamp_imbalance_factor("x") == 1.0
    assert gl.clamp_imbalance_factor(9) == gl.MAX_IMBALANCE_FACTOR
