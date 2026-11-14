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
            "voltage_sensor": "", "phase": "", "indoor_units": [], "max_setpoint_c": 24.0, "apply_setpoint": False,
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


def unit(entity_id="climate.a", mode="heat", setpoint=20.0, **kw):
    kw.setdefault("min_c", 16.0)
    kw.setdefault("max_c", 30.0)
    kw.setdefault("step_c", 0.5)
    return hs.UnitState(entity_id, mode, setpoint, **kw)


def plan(units, tracks=None, offset=1.0, cap=24.0):
    return hs.plan_system(tracks or {}, units, offset_c=offset, max_setpoint_c=cap)


def acts(result):
    return {a.entity_id: (a.pre_mode, a.set_to, a.post_mode) for a in result.actions}


class SystemPlanTests(unittest.TestCase):
    def test_every_heating_unit_gets_the_same_setpoint(self) -> None:
        result = plan([unit("climate.a", setpoint=20.0), unit("climate.b", setpoint=22.0)])
        # moyenne 21 + 1 = 22 : A monte à 22, B reste (déjà à 22)
        self.assertEqual(acts(result), {"climate.a": (None, 22.0, None)})
        self.assertEqual(result.tracks["climate.a"], {"mode": "heat", "base": 20.0, "target": 22.0})
        self.assertIsNone(result.tracks.get("climate.b"))  # rien à mémoriser : consigne inchangée

    def test_a_unit_is_never_lowered_below_its_own_setpoint(self) -> None:
        result = plan([unit("climate.a", setpoint=19.0), unit("climate.b", setpoint=23.5)], offset=0.5)
        # moyenne 21,25 + 0,5 = 21,75 → 22 ; B garde 23,5
        self.assertEqual(acts(result), {"climate.a": (None, 22.0, None)})

    def test_off_units_are_turned_on_at_the_common_setpoint_and_remembered(self) -> None:
        result = plan([unit("climate.a", setpoint=20.0), unit("climate.b", mode="off", setpoint=17.0)])
        self.assertEqual(acts(result)["climate.b"], ("heat", 21.0, None))
        self.assertEqual(result.tracks["climate.b"], {"mode": "off", "base": 17.0, "target": 21.0})
        self.assertEqual(result.tracks["climate.a"], {"mode": "heat", "base": 20.0, "target": 21.0})

    def test_nothing_is_turned_on_when_no_unit_is_heating(self) -> None:
        result = plan([unit("climate.a", mode="off"), unit("climate.b", mode="off")])
        self.assertEqual((result.actions, result.tracks), ([], {}))

    def test_units_in_other_modes_or_without_heat_are_left_alone(self) -> None:
        units = [unit("climate.a"), unit("climate.b", mode="cool"), unit("climate.c", mode="off", can_heat=False)]
        self.assertEqual(set(acts(plan(units))), {"climate.a"})

    def test_max_setpoint_caps_the_common_setpoint(self) -> None:
        result = plan([unit("climate.a", setpoint=23.0)], offset=2.0, cap=24.0)
        self.assertEqual(acts(result), {"climate.a": (None, 24.0, None)})
        # Une unité déjà au-dessus du plafond n'est pas baissée.
        self.assertEqual(plan([unit("climate.a", setpoint=25.0)], offset=2.0, cap=24.0).actions, [])

    def test_unit_step_and_bounds_are_respected(self) -> None:
        self.assertEqual(acts(plan([unit(setpoint=20.0, step_c=1.0)], offset=0.5)), {"climate.a": (None, 21.0, None)})
        self.assertEqual(acts(plan([unit(setpoint=29.5, max_c=30.0)], offset=2.0, cap=40.0)), {"climate.a": (None, 30.0, None)})

    def test_state_and_setpoints_are_restored_when_the_offset_drops_to_zero(self) -> None:
        tracks = {
            "climate.a": {"mode": "heat", "base": 20.0, "target": 21.0},
            "climate.b": {"mode": "off", "base": 17.0, "target": 21.0},
        }
        result = plan([unit("climate.a", setpoint=21.0), unit("climate.b", setpoint=21.0)], tracks, offset=0.0)
        self.assertEqual(acts(result), {"climate.a": (None, 20.0, None), "climate.b": (None, 17.0, "off")})
        self.assertEqual(result.tracks, {"climate.a": None, "climate.b": None})

    def test_state_is_restored_when_no_reference_unit_is_left(self) -> None:
        tracks = {"climate.b": {"mode": "off", "base": 17.0, "target": 21.0}}
        result = plan([unit("climate.a", mode="off"), unit("climate.b", setpoint=21.0)], tracks)
        self.assertEqual(acts(result), {"climate.b": (None, 17.0, "off")})

    def test_offset_changes_keep_the_same_remembered_values(self) -> None:
        tracks = {
            "climate.a": {"mode": "heat", "base": 20.0, "target": 21.0},
            "climate.b": {"mode": "off", "base": 17.0, "target": 21.0},
        }
        result = plan([unit("climate.a", setpoint=21.0), unit("climate.b", setpoint=21.0)], tracks, offset=1.5)
        self.assertEqual(acts(result), {"climate.a": (None, 21.5, None), "climate.b": (None, 21.5, None)})
        self.assertEqual(result.tracks["climate.b"], {"mode": "off", "base": 17.0, "target": 21.5})
        # La consigne de la unité allumée redescend avec le décalage (pas de plancher).
        down = plan([unit("climate.a", setpoint=21.5), unit("climate.b", setpoint=21.5)],
                    {k: {**v, "target": 21.5} for k, v in tracks.items()}, offset=0.5)
        self.assertEqual(acts(down)["climate.b"], (None, 20.5, None))

    def test_manual_setpoint_change_becomes_the_new_reference(self) -> None:
        tracks = {"climate.a": {"mode": "heat", "base": 20.0, "target": 21.0}}
        result = plan([unit("climate.a", setpoint=23.0)], tracks, offset=1.0)
        self.assertEqual(result.tracks["climate.a"], {"mode": "heat", "base": 23.0, "target": 24.0})
        self.assertEqual(plan([unit("climate.a", setpoint=23.0)], tracks, offset=0.0).actions, [])

    def test_unit_switched_off_by_the_user_is_not_turned_on_again(self) -> None:
        tracks = {
            "climate.a": {"mode": "heat", "base": 20.0, "target": 21.0},
            "climate.b": {"mode": "off", "base": 17.0, "target": 21.0},
        }
        result = plan([unit("climate.a", setpoint=21.0), unit("climate.b", mode="off", setpoint=21.0)], tracks)
        self.assertEqual(result.tracks["climate.b"], {"suppressed": True})
        self.assertNotIn("climate.b", acts(result))
        # Reste ignorée tant que le décalage dure, puis libérée à la fin.
        again = plan([unit("climate.a", setpoint=21.0), unit("climate.b", mode="off")], {"climate.b": {"suppressed": True}})
        self.assertNotIn("climate.b", acts(again))
        end = plan([unit("climate.b", mode="off")], {"climate.b": {"suppressed": True}}, offset=0.0)
        self.assertEqual(end.tracks, {"climate.b": None})

    def test_unit_switched_off_by_the_user_after_a_raise_is_not_turned_on_again(self) -> None:
        tracks = {"climate.a": {"mode": "heat", "base": 20.0, "target": 21.0}}
        result = plan([unit("climate.a", mode="off", setpoint=21.0), unit("climate.b", setpoint=20.0)], tracks)
        self.assertEqual(result.tracks["climate.a"], {"suppressed": True})
        self.assertNotIn("climate.a", acts(result))

    def test_small_unit_rounding_is_not_a_manual_change(self) -> None:
        tracks = {"climate.a": {"mode": "heat", "base": 20.0, "target": 21.0}}
        result = plan([unit("climate.a", setpoint=21.1)], tracks)
        self.assertEqual(result.tracks["climate.a"]["base"], 20.0)

    def test_invalid_offset_is_treated_as_zero_and_garbage_tracks_are_ignored(self) -> None:
        self.assertEqual(plan([unit()], offset=float("nan")).actions, [])
        self.assertIsNone(hs.clean_track({"mode": "cool", "target": 21}))
        self.assertIsNone(hs.clean_track("x"))
        self.assertEqual(hs.clean_track({"mode": "off", "target": 21.004, "base": "?"}), {"mode": "off", "target": 21.0})
        self.assertEqual(hs.clean_track({"suppressed": True, "base": 3}), {"suppressed": True})


class MaxSetpointTests(unittest.TestCase):
    def test_default_and_bounds(self) -> None:
        self.assertEqual(hs.normalise_system(entry(), "x")[0]["max_setpoint_c"], 24.0)
        self.assertEqual(hs.normalise_system(entry(max_setpoint_c=99), "x")[0]["max_setpoint_c"], 30.0)
        self.assertEqual(hs.normalise_system(entry(max_setpoint_c=5), "x")[0]["max_setpoint_c"], 16.0)
        self.assertEqual(hs.normalise_system(entry(max_setpoint_c="abc"), "x")[0]["max_setpoint_c"], 24.0)
        self.assertEqual(hs.normalise_system(entry(max_setpoint_c=22.5), "x")[0]["max_setpoint_c"], 22.5)


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
