import unittest

import cluster_trade


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse({"id": "abc123"})


class ClusterTradeTests(unittest.TestCase):
    def test_template_metadata_uses_name_fallbacks(self):
        spell = cluster_trade.template_metadata(
            "effect_spell_damage3 - ilvl84",
            {},
        )
        self.assertEqual(spell["base"], "10% increased Spell Damage")
        self.assertEqual(spell["passive_count"], 12)
        self.assertEqual(spell["minimum_item_level"], 84)
        self.assertEqual(spell["item_type"], "Large Cluster Jewel")

        reservation = cluster_trade.template_metadata(
            "Mana Reserv_03-04_02.42 - ilvl84",
            {},
        )
        self.assertEqual(reservation["passive_count"], 3)
        self.assertEqual(reservation["item_type"], "Small Cluster Jewel")

    def test_trade_query_requires_clean_nonunique_exact_base(self):
        metadata = {
            "base": "10% increased Projectile Damage",
            "passive_count": 5,
            "minimum_item_level": 68,
            "item_type": "Medium Cluster Jewel",
        }
        query = cluster_trade.build_trade_query(
            metadata,
            "enchant.stat_3948993189|7",
        )
        body = query["query"]
        misc = body["filters"]["misc_filters"]["filters"]
        types = body["filters"]["type_filters"]["filters"]
        stats = body["stats"][0]["filters"]

        self.assertEqual(body["type"], "Medium Cluster Jewel")
        self.assertEqual(types["rarity"], {"option": "nonunique"})
        self.assertEqual(misc["ilvl"], {"min": 68})
        self.assertEqual(misc["corrupted"], {"option": "false"})
        self.assertEqual(misc["fractured_item"], {"option": "false"})
        self.assertEqual(stats[0], {"id": "enchant.stat_3948993189|7"})
        self.assertEqual(stats[1]["value"], {"min": 4, "max": 5})

    def test_non_medium_passive_counts_remain_exact(self):
        self.assertEqual(cluster_trade.passive_count_range(3), (3, 3))
        self.assertEqual(cluster_trade.passive_count_range(8), (8, 8))
        self.assertEqual(cluster_trade.passive_count_range(12), (12, 12))

    def test_legacy_cluster_option_uses_option_filter(self):
        result = cluster_trade.build_cluster_base_filter("54")
        self.assertEqual(result["id"], "enchant.stat_3948993189")
        self.assertEqual(result["value"], {"option": "54"})

    def test_create_trade_search_posts_and_returns_browser_url(self):
        stats = {
            "result": [
                {
                    "label": "Enchant",
                    "entries": [
                        {
                            "id": "enchant.stat_3948993189|7",
                            "text": "Added Small Passive Skills grant: 10% increased Projectile Damage",
                        }
                    ],
                }
            ]
        }
        data = {
            "cluster_meta": {
                "base": "10% increased Projectile Damage",
                "passive_count": 5,
                "minimum_item_level": 68,
            }
        }
        session = FakeSession()
        url, metadata, payload = cluster_trade.create_trade_search(
            session,
            stats,
            "M5 - Projectile Damage - ilvl68 - 40c+",
            data,
            "Allflame",
        )

        self.assertEqual(
            url,
            "https://www.pathofexile.com/trade/search/Allflame/abc123",
        )
        self.assertEqual(metadata["minimum_item_level"], 68)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(payload, session.calls[0][1]["json"])


if __name__ == "__main__":
    unittest.main()
