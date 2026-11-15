"""Les listes de tarif de Home Assistant et l'écran « Contrat et réseau » restent cohérents."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.domain.tariff.tariff_model import distribution_profile, tariff_dimensions  # noqa: E402
from foxcat_energy.domain.tariff.tariff_prices import (  # noqa: E402
    coherent_tariff_keys,
    tariff_updates_for,
)

CONTRACT = "Contractuelle / fixe"
VARIABLE = "Variable via entités Home Assistant"
DYNAMIC = "Dynamique Day-Ahead"


def apply(settings: dict, key: str, value) -> dict:
    """Rejoue ce que fait le coordinateur quand une liste change."""
    updates = tariff_updates_for(settings, key, value)
    settings.update(updates)
    return settings


def assert_coherent(case: unittest.TestCase, s: dict) -> None:
    expected = coherent_tariff_keys(s["price_source"], s["tariff_structure"])
    for k, v in expected.items():
        case.assertEqual(s[k], v, k)
    dims = tariff_dimensions(s)
    case.assertEqual(dims.structure, s["tariff_structure"])
    case.assertEqual(distribution_profile(s), s["distribution_profile"])


class TariffSelectorSyncTests(unittest.TestCase):
    def test_every_selector_change_keeps_all_keys_coherent(self) -> None:
        settings = {"price_source": VARIABLE, "tariff_structure": "Simple"}
        changes = [
            ("tariff_structure", "Impact"), ("price_source", DYNAMIC), ("tariff_structure", "Bi-horaire"),
            ("tariff_regime", "Mono-horaire"), ("distribution_profile", "Impact"),
            ("dynamic_structure", "Bi-horaire"), ("price_source", CONTRACT),
            ("tariff_regime", "Dynamique"), ("tariff_regime", "Bi-horaire (HP/HC)"),
            ("distribution_profile", "Simple"), ("dynamic_structure", "Impact (Capacitaire)"),
        ]
        for key, value in changes:
            apply(settings, key, value)
            assert_coherent(self, settings)

    def test_structure_is_independent_of_the_contract(self) -> None:
        s = apply({"price_source": CONTRACT, "tariff_structure": "Simple"}, "tariff_structure", "Impact")
        self.assertEqual((s["price_source"], s["tariff_structure"], s["tariff_regime"]),
                         (CONTRACT, "Impact", "Mono-horaire"))
        s = apply(s, "price_source", DYNAMIC)
        self.assertEqual((s["tariff_structure"], s["tariff_regime"], s["tariff_family"]),
                         ("Impact", "Dynamique", "dynamique"))

    def test_regime_list_matches_the_menu_for_contract_and_structure(self) -> None:
        s = apply({"price_source": DYNAMIC, "tariff_structure": "Impact"}, "tariff_regime", "Bi-horaire (HP/HC)")
        self.assertEqual((s["price_source"], s["tariff_structure"], s["distribution_profile"]),
                         (VARIABLE, "Bi-horaire", "Bi-horaire (jour / nuit)"))

    def test_regime_dynamic_keeps_the_structure(self) -> None:
        s = apply({"price_source": CONTRACT, "tariff_structure": "Bi-horaire"}, "tariff_regime", "Dynamique")
        self.assertEqual((s["price_source"], s["tariff_structure"]), (DYNAMIC, "Bi-horaire"))

    def test_distribution_profile_list_updates_structure_and_regime(self) -> None:
        s = apply({"price_source": CONTRACT, "tariff_structure": "Simple"}, "distribution_profile", "Bi-horaire (jour / nuit)")
        self.assertEqual((s["tariff_structure"], s["tariff_regime"]), ("Bi-horaire", "Bi-horaire (HP/HC)"))

    def test_external_integration_stays_dynamic(self) -> None:
        s = apply({"price_source": "Intégration externe", "tariff_structure": "Simple"}, "tariff_structure", "Impact")
        self.assertEqual((s["price_source"], s["tariff_family"], s["tariff_regime"]),
                         ("Intégration externe", "dynamique", "Dynamique"))

    def test_menu_and_lists_produce_the_same_keys(self) -> None:
        for source in (CONTRACT, VARIABLE, DYNAMIC):
            for structure in ("Simple", "Bi-horaire", "Impact"):
                via_menu = coherent_tariff_keys(source, structure)
                s = {"price_source": VARIABLE, "tariff_structure": "Simple"}
                apply(s, "price_source", source)
                apply(s, "tariff_structure", structure)
                self.assertEqual({k: s[k] for k in via_menu}, via_menu, (source, structure))

    def test_unknown_values_fall_back_to_simple(self) -> None:
        s = apply({"price_source": VARIABLE, "tariff_structure": "Bi-horaire"}, "tariff_structure", "n'importe quoi")
        self.assertEqual(s["tariff_structure"], "Simple")


if __name__ == "__main__":
    unittest.main()
