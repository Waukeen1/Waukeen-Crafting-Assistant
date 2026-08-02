import unittest

from tools.audit_cluster_template_market import (
    canonical_text,
    enumerate_notable_combinations,
    exact_candidate_query,
    parse_medium_pools,
    price_candidate_results,
    price_groups,
    scan_candidate_universe,
    scan_grouped_triple_universe,
    scan_medium_candidate_universe,
    triple_partition_jobs,
)


class ClusterTemplateMarketAuditTests(unittest.TestCase):
    def test_medium_pool_parser_reads_every_notable(self):
        html = """
        <table><tbody><tr><td>
          <a href="/us/Medium_Cluster_Jewel_test">
            <span class="explicitMod"><span class="mod-value">12</span>% increased Test Damage</span>
          </a>
          <div><table><tbody>
            <tr><td><a class="PassiveSkills">Alpha</a></td><td>100</td><td>1</td><td>Prefix</td></tr>
            <tr><td><a class="PassiveSkills">Beta</a></td><td>50</td><td>68</td><td>Prefix</td></tr>
            <tr><td><a class="PassiveSkills">Gamma</a></td><td>50</td><td>75</td><td>Suffix</td></tr>
          </tbody></table></div>
        </td></tr></tbody></table>
        """
        pools = parse_medium_pools(
            html,
            {"Alpha": "a", "Beta": "b", "Gamma": "c"},
        )
        pool = pools[canonical_text("12% increased Test Damage")]
        self.assertEqual(
            [notable["notableName"] for notable in pool["notables"]],
            ["Alpha", "Beta", "Gamma"],
        )

    def test_candidate_generation_is_exhaustive_and_level_aware(self):
        notables = [
            {"notableName": "A", "level": 1, "side": "prefix"},
            {"notableName": "B", "level": 68, "side": "prefix"},
            {"notableName": "C", "level": 75, "side": "suffix"},
        ]
        self.assertEqual(
            enumerate_notable_combinations(notables, 2, 68),
            [("A", "B")],
        )
        self.assertEqual(
            set(enumerate_notable_combinations(notables, 2, 75)),
            {("A", "B"), ("A", "C"), ("B", "C")},
        )

    def test_three_notable_candidate_respects_affix_capacity(self):
        notables = [
            {"notableName": "A", "level": 1, "side": "prefix"},
            {"notableName": "B", "level": 1, "side": "prefix"},
            {"notableName": "C", "level": 1, "side": "prefix"},
            {"notableName": "D", "level": 1, "side": "suffix"},
        ]
        combos = set(enumerate_notable_combinations(notables, 3, 1))
        self.assertNotIn(("A", "B", "C"), combos)
        self.assertIn(("A", "B", "D"), combos)

    def test_price_filter_uses_complete_group_floor(self):
        record = {
            "scanned_at": "now",
            "trade_url": "trade",
            "groups": {
                "A|B": {"prices": [55, 60, 70]},
                "C|D": {"prices": [35, 100, 200]},
            },
        }
        accepted = price_groups(record, minimum_chaos=50, minimum_listings=2)
        self.assertEqual([combo for combo, _ in accepted], [("A", "B")])

    def test_exact_query_contains_only_selected_candidate(self):
        base_query = {
            "query": {
                "stats": [
                    {"type": "and", "filters": [{"id": "base"}]},
                    {"type": "count", "filters": [{"id": "all-pool"}]},
                ]
            }
        }
        query = exact_candidate_query(
            base_query,
            ("A", "B"),
            {
                "A": {"notableId": "a"},
                "B": {"notableId": "b"},
                "C": {"notableId": "c"},
            },
        )
        self.assertEqual(
            query["query"]["stats"][1],
            {"type": "and", "filters": [{"id": "a"}, {"id": "b"}]},
        )
        self.assertEqual(base_query["query"]["stats"][1]["type"], "count")

    def test_candidate_prices_use_total_popularity_and_first_ten_sample(self):
        record = {
            "candidate_results": {
                "A|B": {
                    "total": 12,
                    "prices": [55, 60],
                    "trade_url": "trade",
                },
                "C|D": {"total": 1, "prices": [100]},
            }
        }
        accepted = price_candidate_results(
            record, minimum_chaos=50, minimum_listings=3
        )
        self.assertEqual([combo for combo, _ in accepted], [("A", "B")])

    def test_partial_scan_is_checkpointed_but_never_complete(self):
        class FakeRequester:
            def __init__(self):
                self.searches = 0

            def send_request(self, url, data=None, is_fetch=False):
                if is_fetch:
                    return {"result": []}
                self.searches += 1
                return {"id": f"q{self.searches}", "total": 0, "result": []}

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            cache = {}
            record = scan_candidate_universe(
                cache,
                Path(folder) / "cache.json",
                "key",
                FakeRequester(),
                "League",
                {"query": {"stats": [{"type": "and", "filters": []}]}},
                [("A", "B"), ("A", "C")],
                {
                    "A": {"notableId": "a"},
                    "B": {"notableId": "b"},
                    "C": {"notableId": "c"},
                    "D": {"notableId": "d"},
                },
                {},
                maximum_new_candidates=1,
            )
        self.assertFalse(record["complete"])
        self.assertEqual(record["candidates_scanned"], 1)

    def test_medium_partition_covers_all_pairs_with_grouped_queries(self):
        class FakeRequester:
            def __init__(self):
                self.searches = 0

            def send_request(self, url, data=None, is_fetch=False):
                self.searches += 1
                return {"id": f"q{self.searches}", "total": 0, "result": []}

        import tempfile
        from pathlib import Path

        requester = FakeRequester()
        with tempfile.TemporaryDirectory() as folder:
            record = scan_medium_candidate_universe(
                {},
                Path(folder) / "cache.json",
                "key",
                requester,
                "League",
                {"query": {"stats": [{"type": "and", "filters": []}]}},
                [("A", "B"), ("A", "C"), ("B", "C")],
                {
                    "A": {"notableId": "a"},
                    "B": {"notableId": "b"},
                    "C": {"notableId": "c"},
                    "D": {"notableId": "d"},
                },
                {},
            )
        self.assertTrue(record["complete"])
        self.assertEqual(set(record["candidate_results"]), {"A|B", "A|C", "B|C"})
        self.assertEqual(requester.searches, 2)

    def test_single_candidate_partition_fetches_only_ten_listings(self):
        class FakeRequester:
            def __init__(self):
                self.fetch_count = 0

            def send_request(self, url, data=None, is_fetch=False):
                if is_fetch:
                    from urllib.parse import unquote

                    result_ids = url.split("/fetch/", 1)[1].split("?", 1)[0]
                    self.fetch_count = len(unquote(result_ids).split(","))
                    return {"result": []}
                return {
                    "id": "query",
                    "total": 50,
                    "result": [f"id-{index}" for index in range(50)],
                }

        import tempfile
        from pathlib import Path

        requester = FakeRequester()
        with tempfile.TemporaryDirectory() as folder:
            record = scan_medium_candidate_universe(
                {},
                Path(folder) / "cache.json",
                "key",
                requester,
                "League",
                {"query": {"stats": [{"type": "and", "filters": []}]}},
                [("A", "B")],
                {
                    "A": {"notableId": "a"},
                    "B": {"notableId": "b"},
                },
                {},
            )
        self.assertTrue(record["complete"])
        self.assertEqual(requester.fetch_count, 10)

    def test_large_eight_partition_jobs_cover_each_triple_once(self):
        entries = {
            name: {"notableId": name.lower(), "side": "prefix"}
            for name in ("A", "B", "C", "D")
        }
        universe = [
            ("A", "B", "C"),
            ("A", "B", "D"),
            ("A", "C", "D"),
            ("B", "C", "D"),
        ]
        jobs = triple_partition_jobs(universe, entries)
        expanded = [
            tuple(sorted((*required, partner)))
            for required, partners in jobs
            for partner in partners
        ]
        self.assertEqual(len(expanded), len(set(expanded)))
        self.assertEqual(set(expanded), set(universe))

    def test_large_twelve_partition_jobs_cover_prefix_suffix_suffix_once(self):
        entries = {
            "P1": {"id": "p1", "side": "prefix"},
            "P2": {"id": "p2", "side": "prefix"},
            "S1": {"id": "s1", "side": "suffix"},
            "S2": {"id": "s2", "side": "suffix"},
            "S3": {"id": "s3", "side": "suffix"},
        }
        universe = [
            tuple(sorted((prefix, left, right)))
            for prefix in ("P1", "P2")
            for left, right in (("S1", "S2"), ("S1", "S3"), ("S2", "S3"))
        ]
        jobs = triple_partition_jobs(universe, entries, l12=True)
        expanded = [
            tuple(sorted((*required, partner)))
            for required, partners in jobs
            for partner in partners
        ]
        self.assertEqual(len(expanded), len(set(expanded)))
        self.assertEqual(set(expanded), set(universe))

    def test_grouped_large_scan_checkpoints_every_candidate(self):
        class FakeRequester:
            def __init__(self):
                self.searches = 0

            def send_request(self, url, data=None, is_fetch=False):
                self.searches += 1
                return {"id": f"q{self.searches}", "total": 0, "result": []}

        import tempfile
        from pathlib import Path

        entries = {
            name: {"notableId": name.lower(), "side": "prefix"}
            for name in ("A", "B", "C", "D")
        }
        universe = [
            ("A", "B", "C"),
            ("A", "B", "D"),
            ("A", "C", "D"),
            ("B", "C", "D"),
        ]
        requester = FakeRequester()
        with tempfile.TemporaryDirectory() as folder:
            record = scan_grouped_triple_universe(
                {},
                Path(folder) / "cache.json",
                "key",
                requester,
                "League",
                {"query": {"stats": [{"type": "and", "filters": []}]}},
                universe,
                entries,
                {},
                triple_partition_jobs(universe, entries),
            )
        self.assertTrue(record["complete"])
        self.assertEqual(
            set(record["candidate_results"]),
            {"A|B|C", "A|B|D", "A|C|D", "B|C|D"},
        )
        self.assertEqual(requester.searches, 3)


if __name__ == "__main__":
    unittest.main()
