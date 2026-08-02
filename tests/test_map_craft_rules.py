import json
import unittest
from pathlib import Path

import map_craft_rules as rules


ROOT = Path(__file__).resolve().parents[1]

NORMAL_T16 = """Item Class: Maps
Rarity: Normal
Test Map
--------
Map Tier: 16
--------
"""

CORRUPTED_T16 = """Item Class: Maps
Rarity: Rare
Test Map
--------
Map Tier: 16
--------
Item Quantity: +90% (augmented)
Item Rarity: +45% (augmented)
Monster Pack Size: +30% (augmented)
--------
Monsters deal 100% extra Damage
--------
Corrupted
"""


class MapCraftRulesTests(unittest.TestCase):
    def test_production_affix_pool_is_populated(self):
        groups = rules.load_affix_groups(ROOT / "data" / "map_mods.json")
        affixes = rules.unique_affixes(groups)
        self.assertGreaterEqual(len(groups), 100)
        self.assertGreaterEqual(len(affixes), 100)
        self.assertIn("Area contains many Totems", affixes)
        self.assertIn(
            "Rare Monsters have Elemental Thorns reflecting # Elemental Damage",
            affixes,
        )
        self.assertNotIn("Monsters reflect 18% of Elemental Damage", affixes)
        self.assertNotIn("Monsters reflect 20% of Elemental Damage", affixes)

    def test_elemental_bow_templates_use_current_thorns_mod(self):
        current_mod = (
            "Rare Monsters have Elemental Thorns reflecting # Elemental Damage"
        )
        retired_mods = {
            "Monsters reflect 18% of Elemental Damage",
            "Monsters reflect 20% of Elemental Damage",
        }
        for name in (
            "Waukeen Elemental Bow.json",
            "Waukeen Elemental Bow - Memory Nightmare.json",
        ):
            template = json.loads((ROOT / "mapcraft" / name).read_text(encoding="utf-8"))
            for key in ("map_normal_forbidden", "map_memory_forbidden"):
                blacklist = template[key]
                self.assertIn(current_mod, blacklist)
                self.assertTrue(retired_mods.isdisjoint(blacklist))

    def test_profile_selects_its_own_blacklist(self):
        settings = {
            "map_profile": rules.PROFILE_NORMAL,
            "map_normal_forbidden": ["normal-only"],
            "map_memory_forbidden": ["memory-only"],
        }
        self.assertEqual(rules.active_forbidden(settings), ["normal-only"])
        settings["map_profile"] = rules.PROFILE_MEMORY_NIGHTMARE
        self.assertEqual(rules.active_forbidden(settings), ["memory-only"])

    def test_legacy_forbidden_list_still_loads_for_normal_profile(self):
        settings = {
            "map_profile": rules.PROFILE_NORMAL,
            "map_forbidden": ["legacy"],
        }
        self.assertEqual(rules.active_forbidden(settings), ["legacy"])

    def test_only_quantity_rarity_and_pack_thresholds_are_evaluated(self):
        settings = {
            "map_quantity_thresh": 80,
            "map_rarity_thresh": 40,
            "map_pack_size_thresh": 25,
            "map_currency_thresh": 999,
            "map_scarab_thresh": 999,
            "map_divination_thresh": 999,
        }
        result = rules.evaluate(
            0,
            {"quantity": 90, "rarity": 45, "pack_size": 30},
            settings,
        )
        self.assertTrue(result["accepted"])

    def test_blacklist_or_threshold_failure_rejects_map(self):
        settings = {
            "map_quantity_thresh": 80,
            "map_rarity_thresh": 40,
            "map_pack_size_thresh": 25,
        }
        result = rules.evaluate(
            1,
            {"quantity": 70, "rarity": 45, "pack_size": 30},
            settings,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["forbidden_count"], 1)
        self.assertEqual(result["threshold_failures"], ["Quantity=70/80"])

    def test_alchemy_vaal_accepts_normal_or_rare_t16_map(self):
        self.assertEqual(rules.alchemy_vaal_start_failures(NORMAL_T16), [])
        self.assertEqual(
            rules.alchemy_vaal_start_failures(
                NORMAL_T16.replace("Rarity: Normal", "Rarity: Rare")
            ),
            [],
        )
        self.assertTrue(
            rules.alchemy_vaal_start_failures(
                NORMAL_T16.replace("Map Tier: 16", "Map Tier: 15")
            )
        )
        self.assertTrue(
            rules.alchemy_vaal_start_failures(
                NORMAL_T16.replace("Rarity: Normal", "Rarity: Magic")
            )
        )

    def test_map_tier_parser_accepts_short_and_augmented_lines(self):
        self.assertEqual(rules.parse_map_tier("Tier: 16"), 16)
        self.assertEqual(rules.parse_map_tier("Map Tier: 16 (augmented)"), 16)

    def test_batch_can_allow_missing_tier_but_rejects_explicit_wrong_tier(self):
        missing_tier = NORMAL_T16.replace("Map Tier: 16\n", "")
        self.assertEqual(
            rules.alchemy_vaal_start_failures(
                missing_tier,
                allow_missing_tier=True,
            ),
            [],
        )
        self.assertEqual(
            rules.alchemy_vaal_start_failures(
                NORMAL_T16.replace("Map Tier: 16", "Tier: 15"),
                allow_missing_tier=True,
            ),
            ["Map Tier=15 (hedef 16)"],
        )

    def test_corrupted_identified_result_can_pass(self):
        settings = {
            "map_quantity_thresh": 80,
            "map_rarity_thresh": 40,
            "map_pack_size_thresh": 25,
        }
        failures = rules.alchemy_vaal_final_failures(
            CORRUPTED_T16,
            0,
            {"quantity": 90, "rarity": 45, "pack_size": 30},
            settings,
        )
        self.assertEqual(failures, [])

    def test_unidentified_result_is_fail_closed(self):
        failures = rules.alchemy_vaal_final_failures(
            CORRUPTED_T16 + "\nUnidentified\n",
            0,
            {"quantity": 90, "rarity": 45, "pack_size": 30},
            {},
        )
        self.assertIn("Unidentified: modlar doğrulanamıyor", failures)

    def test_final_result_requires_corruption_and_respects_blacklist(self):
        failures = rules.alchemy_vaal_final_failures(
            CORRUPTED_T16.replace("\nCorrupted\n", "\n"),
            2,
            {"quantity": 90, "rarity": 45, "pack_size": 30},
            {},
        )
        self.assertIn("Vaal uygulanmamış", failures)
        self.assertIn("2 istenmeyen mod", failures)


if __name__ == "__main__":
    unittest.main()
