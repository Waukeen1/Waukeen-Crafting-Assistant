import unittest

import map_craft_rules as rules


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
