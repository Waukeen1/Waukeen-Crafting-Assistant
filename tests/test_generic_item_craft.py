import json
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

    def test_chance_loop_uses_chance_on_normal_item(self):
        action, _ = item_craft.choose_chance_to_unique_action("Normal")
        self.assertEqual(action, "chance")

    def test_chance_loop_scours_magic_and_rare_results(self):
        for rarity in ("Magic", "Rare"):
            with self.subTest(rarity=rarity):
                action, _ = item_craft.choose_chance_to_unique_action(rarity)
                self.assertEqual(action, "scour")

    def test_chance_loop_stops_immediately_on_unique(self):
        action, _ = item_craft.choose_chance_to_unique_action("Unique")
        self.assertEqual(action, "done")

    def test_chance_loop_stops_on_unknown_rarity(self):
        action, _ = item_craft.choose_chance_to_unique_action("Unknown")
        self.assertEqual(action, "stop")

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

    def test_item_identity_accepts_superior_and_magic_base_names(self):
        for displayed_name in (
            "Superior Blizzard Crown",
            "Warlord's Blizzard Crown of the Conquest",
        ):
            with self.subTest(displayed_name=displayed_name):
                item_text = "\n".join(
                    [
                        "Item Class: Helmets",
                        "Rarity: Magic",
                        displayed_name,
                        "--------",
                        "Quality: +20%",
                        "Item Level: 85",
                        "Shaper Item",
                    ]
                )
                valid, reason, item_level = item_craft.validate_item(
                    item_text,
                    "Blizzard Crown",
                    "Shaper",
                )
                self.assertTrue(valid, reason)
                self.assertEqual(item_level, 85)

    def test_item_identity_does_not_match_base_name_outside_header(self):
        item_text = "\n".join(
            [
                "Item Class: Helmets",
                "Rarity: Normal",
                "Superior Hubris Circlet",
                "--------",
                "Note: Blizzard Crown",
                "Item Level: 85",
                "Shaper Item",
            ]
        )
        valid, _, _ = item_craft.validate_item(
            item_text,
            "Blizzard Crown",
            "Shaper",
        )
        self.assertFalse(valid)

    def test_warlord_blizzard_crown_preset_targets_t1_crit_multi(self):
        preset_path = (
            ROOT
            / "genericitemcraft"
            / "Warlord Blizzard Crown - Crit Multi.json"
        )
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
        self.assertEqual(preset["item_level"], 85)
        self.assertEqual(
            preset["item_target_ids"],
            ["CriticalStrikeMultiplierInfluence3"],
        )

    def test_spine_bow_parser_finds_additional_arrows_not_weapon_stats(self):
        item_text = "\n".join(
            [
                "Item Class: Bows",
                "Rarity: Magic",
                "Glaciated Spine Bow of Many",
                "--------",
                "Quality: +25% (augmented)",
                "Physical Damage: 48-144 (augmented)",
                "Elemental Damage: 94-160 (augmented)",
                "Critical Strike Chance: 6.50%",
                "Attacks per Second: 1.40",
                "--------",
                "Requirements:",
                "Level: 68",
                "Dex: 212",
                "--------",
                "Sockets: G-G-G-G-G-G",
                "--------",
                "Item Level: 87",
                "--------",
                "Adds 94 to 160 Cold Damage",
                "Bow Attacks fire 2 additional Arrows",
                "--------",
            ]
        )
        rarity, mods, item_level = item_craft.parse_item_for_craft(
            self.catalog,
            "Spine Bow",
            "None",
            item_text,
        )
        self.assertEqual(rarity, "Magic")
        self.assertEqual(item_level, 87)
        self.assertEqual(
            mods,
            [
                "Adds 94 to 160 Cold Damage",
                "Bow Attacks fire 2 additional Arrows",
            ],
        )

        summary = item_craft.analyze(
            self.catalog,
            "Spine Bow",
            "None",
            item_level,
            mods,
            ["AdditionalArrowBow2_"],
            1,
        )
        action, _ = item_craft.choose_action(
            rarity,
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(summary["affix_count"], 2)
        self.assertEqual(summary["suffix_count"], 1)
        self.assertEqual(action, "done")

    def test_full_item_text_uses_augment_for_missing_prefix_after_suffix(self):
        item_text = "\n".join(
            [
                "Item Class: Helmets",
                "Rarity: Magic",
                "Blizzard Crown of the Drake",
                "--------",
                "Quality: +20% (augmented)",
                "Evasion Rating: 253 (augmented)",
                "Energy Shield: 52 (augmented)",
                "--------",
                "Requirements:",
                "Level: 75",
                "--------",
                "Item Level: 85",
                "--------",
                "+30% to Fire Resistance",
                "--------",
                "Warlord Item",
            ]
        )
        rarity, mods, item_level = item_craft.parse_item_for_craft(
            self.catalog,
            "Blizzard Crown",
            "Warlord",
            item_text,
        )
        summary = item_craft.analyze(
            self.catalog,
            "Blizzard Crown",
            "Warlord",
            item_level,
            mods,
            ["MaximumPowerChargeInfluence1"],
            1,
        )
        action, _ = item_craft.choose_action(
            rarity,
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(mods, ["+30% to Fire Resistance"])
        self.assertEqual(action, "augment")

    def test_full_item_text_uses_alter_for_missing_prefix_after_prefix(self):
        item_text = "\n".join(
            [
                "Item Class: Helmets",
                "Rarity: Magic",
                "Healthy Blizzard Crown",
                "--------",
                "Quality: +20% (augmented)",
                "Evasion Rating: 253 (augmented)",
                "Energy Shield: 52 (augmented)",
                "--------",
                "Requirements:",
                "Level: 75",
                "--------",
                "Item Level: 85",
                "--------",
                "+60 to maximum Life",
                "--------",
                "Warlord Item",
            ]
        )
        rarity, mods, item_level = item_craft.parse_item_for_craft(
            self.catalog,
            "Blizzard Crown",
            "Warlord",
            item_text,
        )
        summary = item_craft.analyze(
            self.catalog,
            "Blizzard Crown",
            "Warlord",
            item_level,
            mods,
            ["MaximumPowerChargeInfluence1"],
            1,
        )
        action, _ = item_craft.choose_action(
            rarity,
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(mods, ["+60 to maximum Life"])
        self.assertEqual(action, "alter")

    def test_magic_affix_overflow_fails_closed(self):
        summary = self.analyze_power_charge(
            [
                "Bow",
                "Quality: +25%",
                "Physical Damage: 48-144",
                "Critical Strike Chance: 6.50%",
                "Attacks per Second: 1.40",
            ]
        )
        action, reason = item_craft.choose_action(
            "Magic",
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(action, "stop")
        self.assertIn("Parser guvenlik hatasi", reason)

    def test_flask_pool_contains_only_flask_domain_mods(self):
        flask_mods = item_craft.eligible_mods(
            self.catalog,
            "Granite Flask",
            "None",
            85,
        )
        self.assertTrue(flask_mods)
        self.assertTrue(
            all(mod.get("domain") == "flask" for mod in flask_mods)
        )
        self.assertIn(
            "FlaskBuffMovementSpeedWhileHealing3",
            {mod["id"] for mod in flask_mods},
        )

        helmet_mods = item_craft.eligible_mods(
            self.catalog,
            "Blizzard Crown",
            "None",
            85,
        )
        self.assertFalse(
            any(mod.get("domain") == "flask" for mod in helmet_mods)
        )

    def test_base_suggestions_start_after_three_characters(self):
        self.assertEqual(
            item_craft.matching_base_names(self.catalog, "gr"),
            [],
        )
        matches = item_craft.matching_base_names(self.catalog, "gra")
        self.assertIn("Granite Flask", matches)
        self.assertNotIn("Quicksilver Flask", matches)
        self.assertEqual(
            item_craft.matching_base_names(self.catalog, "CRO"),
            item_craft.matching_base_names(self.catalog, "cro"),
        )

    def test_flask_tooltip_parses_affixes_and_stops_on_target(self):
        item_text = "\n".join(
            [
                "Item Class: Utility Flasks",
                "Rarity: Magic",
                "Alchemist's Granite Flask of the Cheetah",
                "--------",
                "Lasts 4.20 Seconds",
                "Consumes 30 of 60 Charges on use",
                "Currently has 0 Charges",
                "+1500 to Armour",
                "--------",
                "Requirements:",
                "Level: 27",
                "--------",
                "Item Level: 85",
                "--------",
                "27% reduced Duration",
                "25% increased effect",
                "14% increased Movement Speed during Effect",
                "--------",
                "Right click to drink.",
            ]
        )
        rarity, mods, item_level = item_craft.parse_item_for_craft(
            self.catalog,
            "Granite Flask",
            "None",
            item_text,
        )
        self.assertEqual(rarity, "Magic")
        self.assertEqual(item_level, 85)
        self.assertEqual(
            mods,
            [
                "27% reduced Duration",
                "25% increased effect",
                "14% increased Movement Speed during Effect",
            ],
        )

        summary = item_craft.analyze(
            self.catalog,
            "Granite Flask",
            "None",
            item_level,
            mods,
            ["FlaskBuffMovementSpeedWhileHealing3"],
            1,
        )
        action, _ = item_craft.choose_action(
            rarity,
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(summary["affix_count"], 2)
        self.assertEqual(action, "done")

    def test_flask_prefix_uses_augment_for_suffix_target(self):
        summary = item_craft.analyze(
            self.catalog,
            "Granite Flask",
            "None",
            85,
            ["27% reduced Duration", "25% increased effect"],
            ["FlaskBuffMovementSpeedWhileHealing3"],
            1,
        )
        action, _ = item_craft.choose_action(
            "Magic",
            summary,
            {"item_use_augment": True},
        )
        self.assertEqual(summary["prefix_count"], 1)
        self.assertEqual(summary["suffix_count"], 0)
        self.assertEqual(action, "augment")


if __name__ == "__main__":
    unittest.main()
