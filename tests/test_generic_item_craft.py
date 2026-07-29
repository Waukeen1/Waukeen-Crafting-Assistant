import unittest
from pathlib import Path

import generic_item_craft as item_craft


ROOT = Path(__file__).resolve().parents[1]


class GenericItemCraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = item_craft.load_catalog(ROOT / "data" / "item_affixes.json")

    def analyze_power_charge(self, mods):
        return item_craft.analyze(
            self.catalog,
            "Blizzard Crown",
            "Warlord",
            75,
            mods,
            ["MaximumPowerChargeInfluence1"],
            1,
        )

    def test_warlord_blizzard_pool_contains_exact_power_charge_prefix(self):
        matches = [
            mod
            for mod in item_craft.eligible_mods(
                self.catalog,
                "Blizzard Crown",
                "Warlord",
                75,
            )
            if mod["id"] == "MaximumPowerChargeInfluence1"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["type"], "prefix")
        self.assertEqual(matches[0]["level"], 75)

    def test_single_junk_suffix_uses_augmentation_for_prefix_target(self):
        summary = self.analyze_power_charge(["+30% to Fire Resistance"])
        action, _ = item_craft.choose_action(
            "Magic",
            summary,
            {"item_use_augment": True, "item_use_regal": False},
        )
        self.assertEqual(action, "augment")

    def test_single_junk_prefix_does_not_waste_augmentation(self):
        summary = self.analyze_power_charge(["+60 to maximum Life"])
        action, _ = item_craft.choose_action(
            "Magic",
            summary,
            {"item_use_augment": True, "item_use_regal": False},
        )
        self.assertEqual(action, "alter")

    def test_exact_power_charge_roll_finishes_immediately(self):
        summary = self.analyze_power_charge(
            ["+1 to Maximum Power Charges", "+30% to Fire Resistance"]
        )
        action, _ = item_craft.choose_action(
            "Magic",
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(action, "done")

    def test_rare_without_any_target_does_not_waste_exalted_orb(self):
        summary = self.analyze_power_charge(
            ["+60 to maximum Life", "+30% to Fire Resistance", "+25 to Strength"]
        )
        action, _ = item_craft.choose_action(
            "Rare",
            summary,
            {"item_use_exalt": True, "item_use_annul": True},
        )
        self.assertEqual(action, "scour")

    def test_movement_speed_tiers_can_be_or_alternatives(self):
        summary = item_craft.analyze(
            self.catalog,
            "Dragonscale Boots",
            "None",
            86,
            ["30% increased Movement Speed"],
            ["MovementVelocity5", "MovementVelocity6"],
            1,
        )
        self.assertTrue(summary["goal_met"])
        self.assertEqual(summary["matched_count"], 1)

    def test_t1_suppression_is_available_on_matching_base_and_level(self):
        eligible_ids = {
            mod["id"]
            for mod in item_craft.eligible_mods(
                self.catalog,
                "Dragonscale Gauntlets",
                "None",
                85,
            )
        }
        self.assertIn("ChanceToSuppressSpells5__", eligible_ids)

    def test_item_identity_requires_base_influence_and_level(self):
        item_text = "\n".join(
            [
                "Rarity: Magic",
                "Blizzard Crown",
                "--------",
                "Warlord Item",
                "Item Level: 75",
            ]
        )
        valid, _, item_level = item_craft.validate_item(
            item_text,
            "Blizzard Crown",
            "Warlord",
        )
        self.assertTrue(valid)
        self.assertEqual(item_level, 75)
        valid, _, _ = item_craft.validate_item(
            item_text,
            "Blizzard Crown",
            "Hunter",
        )
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
