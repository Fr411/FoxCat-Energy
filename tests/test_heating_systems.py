"""Systèmes de chauffage (PAC) : validation pure du modèle de données."""
import sys
import types
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy import heating_systems as hs  # noqa: E402


def entry(**overrides):
    base = {"name": "Salon", "system_type": "air_air", "power_sensor": "sensor.pac_w"}
    base.update(overrides)
    return base


class NormaliseSystemTests(unittest.TestCase):
    def test_minimal_system_gets_empty_optional_fields(self) -> None:
        record, error = hs.normalise_system(entry(), "id1")
        self.assertIsNone(error)
        self.assertEqual(record, {
            "id": "id1", "name": "Salon", "system_type": "air_air", "power_sensor": "sensor.pac_w",
            "voltage_sensor": "", "phase": "", "indoor_units": [], "apply_setpoint": False,
        })

    def test_name_type_and_power_sensor_are_required(self) -> None:
        for bad in (entry(name=" "), entry(system_type="gaz"), entry(power_sensor=""), entry(system_type=None)):
            self.assertEqual(hs.normalise_system(bad, "x"), (None, hs.ERR_INVALID))

    def test_air_air_keeps_up_to_five_indoor_units_without_duplicates(self) -> None:
        units = [f"climate.u{i}" for i in range(5)]
        record, _ = hs.normalise_system(entry(indoor_units=units + ["climate.u0", ""]), "x")
        self.assertEqual(record["indoor_units"], units)

    def test_six_indoor_units_are_refused(self) -> None:
        units = [f"climate.u{i}" for i in range(6)]
        self.assertEqual(hs.normalise_system(entry(indoor_units=units), "x"), (None, hs.ERR_TOO_MANY_UNITS))

    def test_water_systems_drop_indoor_units(self) -> None:
        units = [f"climate.u{i}" for i in range(9)]
        for kind in ("water_water", "air_water"):
            record, error = hs.normalise_system(entry(system_type=kind, indoor_units=units), "x")
            self.assertIsNone(error)
            self.assertEqual(record["indoor_units"], [])

    def test_voltage_and_phase(self) -> None:
        record, _ = hs.normalise_system(entry(voltage_sensor="sensor.v", phase="l2"), "x")
        self.assertEqual((record["voltage_sensor"], record["phase"]), ("sensor.v", "L2"))
        record, _ = hs.normalise_system(entry(phase="L9"), "x")
        self.assertEqual(record["phase"], "")


    def test_apply_setpoint_needs_air_air_and_indoor_units(self) -> None:
        units = ["climate.a"]
        self.assertTrue(hs.normalise_system(entry(indoor_units=units, apply_setpoint=True), "x")[0]["apply_setpoint"])
        self.assertFalse(hs.normalise_system(entry(apply_setpoint=True), "x")[0]["apply_setpoint"])
        self.assertFalse(hs.normalise_system(entry(system_type="air_water", indoor_units=units, apply_setpoint=True), "x")[0]["apply_setpoint"])
        self.assertFalse(hs.normalise_system(entry(indoor_units=units, apply_setpoint="yes"), "x")[0]["apply_setpoint"])


def plan(track=None, **kw):
    base = {"hvac_mode": "heat", "current_c": 20.0, "offset_c": 1.0, "min_c": 16, "max_c": 30, "step_c": 0.5}
    base.update(kw)
    return hs.plan_setpoint(track, **base)


class SetpointPlanTests(unittest.TestCase):
    def test_first_raise_remembers_the_original_setpoint(self) -> None:
        result = plan()
        self.assertEqual(result.set_to, 21.0)
        self.assertEqual(result.track, {"base": 20.0, "target": 21.0})

    def test_offset_changes_are_applied_on_the_same_base(self) -> None:
        result = plan({"base": 20.0, "target": 21.0}, current_c=21.0, offset_c=1.5)
        self.assertEqual((result.set_to, result.track), (21.5, {"base": 20.0, "target": 21.5}))
        self.assertIsNone(plan({"base": 20.0, "target": 21.0}, current_c=21.0).set_to)  # rien à écrire

    def test_offset_back_to_zero_restores_the_original_setpoint(self) -> None:
        result = plan({"base": 20.3, "target": 21.5}, current_c=21.5, offset_c=0.0)
        self.assertEqual((result.set_to, result.track), (20.3, None))

    def test_no_track_and_no_offset_does_nothing(self) -> None:
        self.assertEqual(plan(offset_c=0.0), hs.SetpointPlan(None, None))

    def test_manual_change_becomes_the_new_base(self) -> None:
        result = plan({"base": 20.0, "target": 21.0}, current_c=23.0, offset_c=1.0)
        self.assertEqual((result.set_to, result.track), (24.0, {"base": 23.0, "target": 24.0}))
        # Décalage nul après une modification manuelle : on ne touche à rien.
        self.assertEqual(plan({"base": 20.0, "target": 21.0}, current_c=23.0, offset_c=0.0), hs.SetpointPlan(None, None))

    def test_small_unit_rounding_is_not_a_manual_change(self) -> None:
        result = plan({"base": 20.0, "target": 21.0}, current_c=21.1, offset_c=1.0)
        self.assertEqual(result.track, {"base": 20.0, "target": 21.0})

    def test_only_the_heating_mode_is_driven(self) -> None:
        for mode in ("cool", "off", "auto", "heat_cool", None):
            self.assertEqual(plan({"base": 20.0, "target": 21.0}, hvac_mode=mode), hs.SetpointPlan(None, None))
        self.assertEqual(plan(current_c=None), hs.SetpointPlan(None, None))
        self.assertEqual(plan(current_c="abc"), hs.SetpointPlan(None, None))

    def test_step_and_bounds_of_the_unit_are_respected(self) -> None:
        self.assertEqual(plan(offset_c=0.5, step_c=1).set_to, 21.0)  # 20.5 arrondi au pas de 1 °C
        self.assertEqual(plan(current_c=29.5, offset_c=2.0, max_c=30).set_to, 30.0)
        self.assertIsNone(plan(current_c=30.0, offset_c=2.0, max_c=30).set_to)

    def test_invalid_offset_is_treated_as_zero(self) -> None:
        self.assertEqual(plan(offset_c=float("nan")), hs.SetpointPlan(None, None))
        self.assertEqual(plan(offset_c=-3.0), hs.SetpointPlan(None, None))


class RecordsTests(unittest.TestCase):
    def test_invalid_or_foreign_items_are_ignored(self) -> None:
        good = hs.normalise_system(entry(), "a")[0]
        options = {hs.CONF_HEATING_SYSTEMS: [good, {"id": "b"}, "x", {"name": "no id", "system_type": "air_air"}]}
        self.assertEqual(hs.records_from(options), [good])
        self.assertEqual(hs.records_from({}), [])
        self.assertEqual(hs.records_from({hs.CONF_HEATING_SYSTEMS: "nope"}), [])

    def test_summary(self) -> None:
        record, _ = hs.normalise_system(entry(indoor_units=["climate.a", "climate.b"]), "a")
        self.assertEqual(hs.summary(record), "Salon — Pompe à chaleur air/air (2 unités)")
        record, _ = hs.normalise_system(entry(system_type="water_water"), "a")
        self.assertEqual(hs.summary(record), "Salon — Pompe à chaleur eau/eau")


if __name__ == "__main__":
    unittest.main()
