import json
from pathlib import Path
import unittest

import flask_craft_guide as guide


ROOT = Path(__file__).resolve().parents[1]


class FlaskCraftGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads(
            (ROOT / "data" / "item_affixes.json").read_text(encoding="utf-8")
        )
        cls.base_names = {base["name"] for base in catalog["bases"]}
        cls.affixes = {mod["affix"] for mod in catalog["mods"]}

    def test_supported_flasks_exist_in_item_catalog(self):
        self.assertGreaterEqual(len(guide.flask_types()), 20)
        self.assertTrue(set(guide.flask_types()).issubset(self.base_names))
        self.assertIn("Topaz Flask", guide.flask_types())
        self.assertIn("Ruby Flask", guide.flask_types())
        self.assertIn("Sapphire Flask", guide.flask_types())
        self.assertIn("Divine Life Flask", guide.flask_types())

    def test_utility_recommendations_use_real_affix_names(self):
        self.assertIn(guide.UTILITY_PREFIX["affix"], self.affixes)
        for suffix in guide.UTILITY_SUFFIXES.values():
            self.assertIn(suffix["affix"], self.affixes)

    def test_every_guide_has_complete_offline_combinations(self):
        for base_name in guide.flask_types():
            record = guide.guide_for(base_name)
            self.assertEqual(record["base"], base_name)
            self.assertTrue(record["offline"])
            self.assertTrue(record["overview"])
            self.assertTrue(record["combinations"])
            for combo in record["combinations"]:
                self.assertTrue(combo["title"])
                self.assertTrue(combo["prefix"])
                self.assertTrue(combo["suffix"])
                self.assertGreaterEqual(combo["min_item_level"], 1)
                self.assertTrue(combo["why"])
                self.assertTrue(combo["finish"])

    def test_elemental_flasks_include_high_value_targets(self):
        topaz_titles = {
            combo["title"] for combo in guide.guide_for("Topaz Flask")["combinations"]
        }
        self.assertIn("25% Effect + of the Owl", topaz_titles)
        self.assertIn("25% Effect + of the Rainbow", topaz_titles)
        self.assertIn("25% Effect + of the Armadillo", topaz_titles)

    def test_life_flask_guide_includes_instant_and_sustain_options(self):
        combinations = guide.guide_for("Divine Life Flask")["combinations"]
        self.assertEqual(combinations[0]["title"], "Seething + Assuaging")
        self.assertEqual(combinations[1]["title"], "Bubbling + Assuaging")
        titles = {combo["title"] for combo in combinations}
        self.assertIn("Seething + Assuaging", titles)
        self.assertIn("Bubbling + Assuaging", titles)
        self.assertIn("Saturated + Perenniality", titles)

    def test_unknown_base_fails_closed(self):
        with self.assertRaises(KeyError):
            guide.guide_for("Not A Flask")


if __name__ == "__main__":
    unittest.main()
