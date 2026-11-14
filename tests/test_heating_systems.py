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
            "voltage_sensor": "", "phase": "", "indoor_units": [],
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
