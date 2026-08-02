import argparse
import hashlib
import itertools
import json
import os
import re
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cluster_arat as scanner


POEDB_CLUSTER_URL = "https://poedb.tw/us/Cluster_Jewel"
POOL_CACHE_PATH = ROOT / "data" / "medium_cluster_notable_pools.json"
AUDIT_VERSION = 3
FETCH_BATCH_SIZE = 10
DEFAULT_MEDIUM_MINIMUM_CHAOS = 40.0
DEFAULT_LARGE_MINIMUM_DIVINE = 2.0
DEFAULT_LARGE_MINIMUM_LISTINGS = 3


def canonical_text(value):
    value = re.sub(
        r"Added Small Passive Skills grant:\s*",
        "",
        str(value or ""),
        flags=re.I,
    )
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {} if default is None else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        for attempt in range(8):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.15 * (attempt + 1))
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def combo_key(combo):
    return "|".join(sorted(combo))


def notable_stat_ids(stats):
    result = {}
    for group in stats.get("result", []):
        for entry in group.get("entries", []):
            text = str(entry.get("text", ""))
            prefix = "1 Added Passive Skill is "
            if text.startswith(prefix) and str(entry.get("id", "")).startswith(
                "explicit.stat_"
            ):
                result[text[len(prefix):]] = entry["id"]
    return result


def parse_medium_pools(html, stat_ids):
    soup = BeautifulSoup(html, "html.parser")
    pools = {}
    selector = 'a[href*="/us/Medium_Cluster_Jewel_"]'
    for anchor in soup.select(selector):
        cell = anchor.find_parent("td")
        table = cell.find("table") if cell else None
        if not table:
            continue
        base = "".join(
            span.get_text(" ", strip=True)
            for span in anchor.select("span.explicitMod")
            if "item_description" not in (span.get("class") or [])
        ).strip()
        if not base:
            base = anchor.get_text(" ", strip=True)
        notables = []
        for row in table.select("tbody > tr"):
            cells = row.find_all("td", recursive=False)
            passive = cells[0].select_one("a.PassiveSkills") if cells else None
            if len(cells) < 4 or not passive:
                continue
            name = passive.get_text(" ", strip=True)
            stat_id = stat_ids.get(name)
            if not stat_id:
                continue
            try:
                level = int(cells[2].get_text(" ", strip=True))
            except ValueError:
                level = 1
            notables.append({
                "notableName": name,
                "level": level,
                "side": cells[3].get_text(" ", strip=True).casefold(),
                "notableId": stat_id,
            })
        if notables:
            pools[canonical_text(base)] = {
                "clusterName": base,
                "notables": notables,
            }
    return pools


def load_medium_pools(stats, refresh=False):
    cached = read_json(POOL_CACHE_PATH)
    if cached and not refresh:
        return cached.get("pools", cached)
    response = requests.get(
        POEDB_CLUSTER_URL,
        headers=scanner.UA,
        timeout=30,
    )
    response.raise_for_status()
    pools = parse_medium_pools(response.text, notable_stat_ids(stats))
    write_json(POOL_CACHE_PATH, {
        "source": POEDB_CLUSTER_URL,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "pools": pools,
    })
    return pools


def find_pool(pools, base):
    wanted = canonical_text(base)
    if wanted in pools:
        return pools[wanted]
    matches = [
        pool for key, pool in pools.items()
        if wanted in key or key in wanted
    ]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"Cluster mod pool was not found for: {base}")


def enumerate_notable_combinations(notables, size, maximum_item_level):
    available = [
        notable for notable in notables
        if int(notable.get("level", 1)) <= int(maximum_item_level)
    ]
    combinations = []
    for combo in itertools.combinations(available, size):
        prefix_count = sum(n.get("side") == "prefix" for n in combo)
        suffix_count = sum(n.get("side") == "suffix" for n in combo)
        if prefix_count <= 2 and suffix_count <= 2:
            combinations.append(tuple(sorted(n["notableName"] for n in combo)))
    return combinations


def combo_hash(combinations):
    payload = "\n".join("|".join(combo) for combo in sorted(combinations))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clean_trade_filters(minimum_item_level):
    return {
        "type_filters": {
            "filters": {
                "category": {"option": "jewel.cluster"},
                "rarity": {"option": "nonunique"},
            }
        },
        "misc_filters": {
            "filters": {
                "ilvl": {"min": int(minimum_item_level)},
                "corrupted": {"option": "false"},
                "fractured_item": {"option": "false"},
            }
        },
        "trade_filters": {
            "filters": {"sale_type": {"option": "priced"}}
        },
    }


def notable_query(metadata, stats, notables, size):
    option_id = scanner.find_cluster_option_id(stats, metadata["base"])
    passive_count = int(metadata["passive_count"])
    passive_min = 4 if passive_count <= 6 else passive_count
    passive_max = 5 if passive_count <= 6 else passive_count
    return {
        "query": {
            "status": {"option": "securable"},
            "type": "Medium Cluster Jewel" if size == 2 else "Large Cluster Jewel",
            "stats": [
                {
                    "type": "and",
                    "filters": [
                        scanner.build_cluster_base_filter(option_id),
                        {
                            "id": "enchant.stat_3086156145",
                            "value": {"min": passive_min, "max": passive_max},
                        },
                    ],
                },
                {
                    "type": "count",
                    "value": {"min": size},
                    "filters": [
                        {"id": notable["notableId"]}
                        for notable in notables
                        if int(notable.get("level", 1))
                        <= int(metadata["minimum_item_level"])
                    ],
                },
            ],
            "filters": clean_trade_filters(metadata["minimum_item_level"]),
        },
        "sort": {"price": "asc"},
    }


def l12_query(metadata, stats, stat_entries):
    option_id = scanner.find_cluster_option_id(stats, metadata["base"])
    return {
        "query": {
            "status": {"option": "securable"},
            "type": "Large Cluster Jewel",
            "stats": [
                {
                    "type": "and",
                    "filters": [
                        scanner.build_cluster_base_filter(option_id),
                        {
                            "id": "enchant.stat_3086156145",
                            "value": {"min": 12, "max": 12},
                        },
                    ],
                },
                {
                    "type": "and",
                    "filters": [{
                        "id": scanner.find_effect_stat_id(stats),
                        "value": {"min": 35},
                    }],
                },
                {
                    "type": "count",
                    "value": {"min": 3},
                    "filters": [
                        {"id": entry["id"], "value": {"min": entry["min"]}}
                        for entry in stat_entries.values()
                    ],
                },
            ],
            "filters": clean_trade_filters(metadata["minimum_item_level"]),
        },
        "sort": {"price": "asc"},
    }


def exact_candidate_query(base_query, combo, entries_by_name, effect_stat_id=None):
    """Narrow a pool query to one candidate so the trade API's 100-id cap is harmless."""
    query = json.loads(json.dumps(base_query))
    fixed_filters = []
    if effect_stat_id:
        fixed_filters.append({"id": effect_stat_id, "value": {"min": 35}})
    for name in combo:
        entry = entries_by_name[name]
        trade_filter = {"id": entry.get("notableId") or entry["id"]}
        if entry.get("min") is not None:
            trade_filter["value"] = {"min": entry["min"]}
        fixed_filters.append(trade_filter)
    query["query"]["stats"] = [
        query["query"]["stats"][0],
        {"type": "and", "filters": fixed_filters},
    ]
    return query


def medium_partition_query(base_query, anchor, partners, entries_by_name):
    query = json.loads(json.dumps(base_query))
    anchor_id = entries_by_name[anchor]["notableId"]
    partner_filters = [
        {"id": entries_by_name[name]["notableId"]} for name in partners
    ]
    query["query"]["stats"] = [
        query["query"]["stats"][0],
        {"type": "and", "filters": [{"id": anchor_id}]},
        {
            "type": "count",
            "value": {"min": 1},
            "filters": partner_filters,
        },
    ]
    return query


def grouped_partition_query(
    base_query,
    required,
    partners,
    entries_by_name,
    effect_stat_id=None,
):
    query = json.loads(json.dumps(base_query))
    required_filters = []
    if effect_stat_id:
        required_filters.append({"id": effect_stat_id, "value": {"min": 35}})
    for name in required:
        entry = entries_by_name[name]
        item = {"id": entry.get("notableId") or entry["id"]}
        if entry.get("min") is not None:
            item["value"] = {"min": entry["min"]}
        required_filters.append(item)
    partner_filters = []
    for name in partners:
        entry = entries_by_name[name]
        item = {"id": entry.get("notableId") or entry["id"]}
        if entry.get("min") is not None:
            item["value"] = {"min": entry["min"]}
        partner_filters.append(item)
    query["query"]["stats"] = [
        query["query"]["stats"][0],
        {"type": "and", "filters": required_filters},
        {"type": "count", "value": {"min": 1}, "filters": partner_filters},
    ]
    return query


def normalize_stat_hash(value):
    value = str(value or "")
    for prefix in ("stat.explicit.", "stat.fractured.", "explicit.", "fractured."):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def explicit_mod_value(mod):
    try:
        magnitude = mod["mods"][0]["magnitudes"][0]
        return float(magnitude.get("max", magnitude.get("min")))
    except (KeyError, IndexError, TypeError, ValueError):
        match = re.search(r"[-+]?\d+(?:\.\d+)?", mod.get("description", ""))
        return float(match.group(0)) if match else None


def extract_notable_combo(item, valid_names, size):
    names = []
    marker = "Added Passive Skill is "
    for mod in item.get("explicitMods", []):
        description = str(mod.get("description", ""))
        if marker not in description:
            continue
        name = description.split(marker, 1)[1].strip()
        if name in valid_names:
            names.append(name)
    unique = tuple(sorted(set(names)))
    return unique if len(unique) == size else None


def extract_l12_combo(item, stat_entries):
    entries_by_id = {
        normalize_stat_hash(entry["id"]): entry
        for entry in stat_entries.values()
    }
    names = []
    for mod in item.get("explicitMods", []):
        entry = entries_by_id.get(normalize_stat_hash(mod.get("hash")))
        if not entry:
            continue
        value = explicit_mod_value(mod)
        if value is not None and value >= entry["min"]:
            names.append(entry["name"])
    unique = tuple(sorted(set(names)))
    return unique if len(unique) == 3 else None


def listing_price_chaos(result, rates):
    try:
        price = result["listing"]["price"]
        rate = rates.get(str(price["currency"]).casefold())
        value = float(price["amount"]) * float(rate)
        return value if value > 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def fetch_market_groups(
    cache,
    cache_path,
    key,
    requester,
    league,
    query,
    extractor,
    rates,
    refresh=False,
):
    if refresh:
        cache.pop(key, None)
    record = cache.get(key) or {}
    if not record.get("result_ids"):
        search = requester.send_request(
            f"{scanner.POE_TRADE_BASE}/search/{league}",
            data=query,
        )
        if not search:
            raise RuntimeError(f"Trade search failed for {key}")
        record = {
            "query_id": search.get("id", ""),
            "trade_url": (
                f"https://www.pathofexile.com/trade/search/{league}/"
                f"{search.get('id', '')}"
            ),
            "total": int(search.get("total", 0)),
            "result_ids": search.get("result", []),
            "next_index": 0,
            "groups": {},
            "complete": False,
        }
        cache[key] = record
        write_json(cache_path, cache)

    ids = record.get("result_ids", [])
    for start in range(int(record.get("next_index", 0)), len(ids), FETCH_BATCH_SIZE):
        batch = ids[start:start + FETCH_BATCH_SIZE]
        url = (
            f"{scanner.POE_TRADE_BASE}/fetch/{quote(','.join(batch))}"
            f"?query={quote(record['query_id'])}"
        )
        fetched = requester.send_request(url, is_fetch=True)
        if not fetched:
            raise RuntimeError(f"Trade fetch failed for {key} at result {start}")
        for result in fetched.get("result", []):
            combo = extractor(result.get("item", {}))
            price = listing_price_chaos(result, rates)
            if not combo or price is None:
                continue
            combo_key = "|".join(combo)
            group = record["groups"].setdefault(combo_key, {"prices": []})
            group["prices"].append(round(price, 4))
        record["next_index"] = start + len(batch)
        cache[key] = record
        write_json(cache_path, cache)

    record["complete"] = True
    record["scanned_at"] = datetime.now(timezone.utc).isoformat()
    cache[key] = record
    write_json(cache_path, cache)
    return record


def fetch_exact_candidate(
    requester,
    league,
    query,
    rates,
):
    search = requester.send_request(
        f"{scanner.POE_TRADE_BASE}/search/{league}",
        data=query,
    )
    if not search:
        raise RuntimeError("Trade search failed")
    query_id = search.get("id", "")
    result_ids = list(search.get("result", []))[:10]
    prices = []
    if result_ids:
        url = (
            f"{scanner.POE_TRADE_BASE}/fetch/{quote(','.join(result_ids))}"
            f"?query={quote(query_id)}"
        )
        fetched = requester.send_request(url, is_fetch=True)
        if not fetched:
            raise RuntimeError("Trade fetch failed")
        for result in fetched.get("result", []):
            price = listing_price_chaos(result, rates)
            if price is not None:
                prices.append(round(price, 4))
    return {
        "total": int(search.get("total", 0)),
        "prices": sorted(prices),
        "trade_url": (
            f"https://www.pathofexile.com/trade/search/{league}/{query_id}"
        ),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_search_results(requester, query_id, result_ids):
    results = []
    for start in range(0, len(result_ids), FETCH_BATCH_SIZE):
        batch = result_ids[start:start + FETCH_BATCH_SIZE]
        url = (
            f"{scanner.POE_TRADE_BASE}/fetch/{quote(','.join(batch))}"
            f"?query={quote(query_id)}"
        )
        fetched = requester.send_request(url, is_fetch=True)
        if not fetched:
            raise RuntimeError("Trade fetch failed")
        results.extend(fetched.get("result", []))
    return results


def scan_medium_candidate_universe(
    cache,
    cache_path,
    key,
    requester,
    league,
    base_query,
    universe,
    entries_by_name,
    rates,
    refresh=False,
):
    """Enumerate all pairs with recursively partitioned, non-overlapping searches."""
    if refresh:
        cache.pop(key, None)
    record = cache.setdefault(key, {
        "audit_version": AUDIT_VERSION,
        "candidate_results": {},
        "partition_results": {},
        "complete": False,
    })
    candidate_results = record.setdefault("candidate_results", {})
    partition_results = record.setdefault("partition_results", {})
    expected = {combo_key(combo) for combo in universe}
    allowed_names = {name for combo in universe for name in combo}
    ordered_names = [name for name in entries_by_name if name in allowed_names]
    for candidate in list(candidate_results):
        if candidate not in expected:
            candidate_results.pop(candidate, None)

    def persist():
        record.update({
            "candidate_count": len(universe),
            "candidates_scanned": len(candidate_results),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        cache[key] = record
        write_json(cache_path, cache)

    def scan_partition(anchor, partners):
        if all(combo_key((anchor, partner)) in candidate_results for partner in partners):
            return
        partition_key = f"{anchor}||{'|'.join(partners)}"
        partition = partition_results.get(partition_key)
        if partition and partition.get("complete"):
            return
        if not partition:
            query = medium_partition_query(
                base_query, anchor, partners, entries_by_name
            )
            search = requester.send_request(
                f"{scanner.POE_TRADE_BASE}/search/{league}", data=query
            )
            if not search:
                raise RuntimeError(f"Trade search failed for {partition_key}")
            partition = {
                "query_id": search.get("id", ""),
                "total": int(search.get("total", 0)),
                "result_ids": list(search.get("result", [])),
                "complete": False,
            }
            partition_results[partition_key] = partition
            persist()

        total = int(partition.get("total", 0))
        if total > 100 and len(partners) > 1:
            middle = len(partners) // 2
            scan_partition(anchor, partners[:middle])
            scan_partition(anchor, partners[middle:])
            partition["complete"] = True
            partition["split"] = True
            persist()
            return

        fetch_limit = 10 if len(partners) == 1 else 100
        results = fetch_search_results(
            requester,
            partition.get("query_id", ""),
            list(partition.get("result_ids", []))[:fetch_limit],
        ) if partition.get("result_ids") else []
        grouped = defaultdict(list)
        unmatched = 0
        valid_names = set(entries_by_name)
        for result in results:
            combo = extract_notable_combo(result.get("item", {}), valid_names, 2)
            price = listing_price_chaos(result, rates)
            if not combo or price is None:
                unmatched += 1
                continue
            grouped[combo_key(combo)].append(round(price, 4))

        # Unexpected three-notable items can make a grouped leaf ambiguous.
        # Split it further rather than silently losing a candidate.
        if unmatched and len(partners) > 1:
            middle = len(partners) // 2
            scan_partition(anchor, partners[:middle])
            scan_partition(anchor, partners[middle:])
            partition["complete"] = True
            partition["split"] = True
            partition["unmatched"] = unmatched
            persist()
            return

        for partner in partners:
            candidate = combo_key((anchor, partner))
            prices = sorted(grouped.get(candidate, []))
            candidate_total = total if len(partners) == 1 else len(prices)
            candidate_results[candidate] = {
                "total": candidate_total,
                "prices": prices[:10],
                "trade_url": (
                    f"https://www.pathofexile.com/trade/search/{league}/"
                    f"{partition.get('query_id', '')}"
                ),
                "scanned_at": datetime.now(timezone.utc).isoformat(),
            }
        partition["complete"] = True
        partition["split"] = False
        persist()
        print(
            f"[PARTITION] {len(candidate_results)}/{len(universe)} "
            f"{anchor} + {len(partners)} partner(s): {total} listings",
            flush=True,
        )

    for index, anchor in enumerate(ordered_names[:-1]):
        scan_partition(anchor, ordered_names[index + 1:])

    record["complete"] = set(candidate_results) == expected
    if record["complete"]:
        record["scanned_at"] = datetime.now(timezone.utc).isoformat()
    persist()
    return record


def extract_notable_names(item, valid_names):
    marker = "Added Passive Skill is "
    names = set()
    for mod in item.get("explicitMods", []):
        description = str(mod.get("description", ""))
        if marker in description:
            name = description.split(marker, 1)[1].strip()
            if name in valid_names:
                names.add(name)
    return names


def extract_l12_names(item, stat_entries):
    entries_by_id = {
        normalize_stat_hash(entry["id"]): entry for entry in stat_entries.values()
    }
    names = set()
    for mod in item.get("explicitMods", []):
        entry = entries_by_id.get(normalize_stat_hash(mod.get("hash")))
        if not entry:
            continue
        value = explicit_mod_value(mod)
        if value is not None and value >= entry["min"]:
            names.add(entry["name"])
    return names


def scan_grouped_triple_universe(
    cache,
    cache_path,
    key,
    requester,
    league,
    base_query,
    universe,
    entries_by_name,
    rates,
    jobs,
    effect_stat_id=None,
    l12=False,
    refresh=False,
):
    if refresh:
        cache.pop(key, None)
    record = cache.setdefault(key, {
        "audit_version": AUDIT_VERSION,
        "candidate_results": {},
        "partition_results": {},
        "complete": False,
    })
    candidate_results = record.setdefault("candidate_results", {})
    partitions = record.setdefault("partition_results", {})
    expected = {combo_key(combo) for combo in universe}
    for candidate in list(candidate_results):
        if candidate not in expected:
            candidate_results.pop(candidate, None)

    def persist():
        record.update({
            "candidate_count": len(universe),
            "candidates_scanned": len(candidate_results),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        cache[key] = record
        write_json(cache_path, cache)

    def scan_partition(required, partners):
        candidate_keys = [combo_key((*required, partner)) for partner in partners]
        if all(candidate in candidate_results for candidate in candidate_keys):
            return
        partition_key = f"{'&'.join(required)}||{'|'.join(partners)}"
        partition = partitions.get(partition_key)
        if partition and partition.get("complete"):
            return
        if not partition:
            query = grouped_partition_query(
                base_query,
                required,
                partners,
                entries_by_name,
                effect_stat_id=effect_stat_id,
            )
            search = requester.send_request(
                f"{scanner.POE_TRADE_BASE}/search/{league}", data=query
            )
            if not search:
                raise RuntimeError(f"Trade search failed for {partition_key}")
            partition = {
                "query_id": search.get("id", ""),
                "total": int(search.get("total", 0)),
                "result_ids": list(search.get("result", [])),
                "complete": False,
            }
            partitions[partition_key] = partition
            persist()

        total = int(partition.get("total", 0))
        if total > 100 and len(partners) > 1:
            middle = len(partners) // 2
            scan_partition(required, partners[:middle])
            scan_partition(required, partners[middle:])
            partition.update({"complete": True, "split": True})
            persist()
            return

        fetch_limit = 10 if len(partners) == 1 else 100
        results = fetch_search_results(
            requester,
            partition.get("query_id", ""),
            list(partition.get("result_ids", []))[:fetch_limit],
        ) if partition.get("result_ids") else []
        grouped = defaultdict(list)
        unmatched = 0
        valid_names = set(entries_by_name)
        for result in results:
            names = (
                extract_l12_names(result.get("item", {}), entries_by_name)
                if l12
                else extract_notable_names(result.get("item", {}), valid_names)
            )
            price = listing_price_chaos(result, rates)
            matched = False
            if price is not None:
                for partner, candidate in zip(partners, candidate_keys):
                    if set((*required, partner)).issubset(names):
                        grouped[candidate].append(round(price, 4))
                        matched = True
            if not matched:
                unmatched += 1

        if unmatched and len(partners) > 1:
            middle = len(partners) // 2
            scan_partition(required, partners[:middle])
            scan_partition(required, partners[middle:])
            partition.update({
                "complete": True,
                "split": True,
                "unmatched": unmatched,
            })
            persist()
            return

        for candidate in candidate_keys:
            prices = sorted(grouped.get(candidate, []))
            candidate_results[candidate] = {
                "total": total if len(partners) == 1 else len(prices),
                "prices": prices[:10],
                "trade_url": (
                    f"https://www.pathofexile.com/trade/search/{league}/"
                    f"{partition.get('query_id', '')}"
                ),
                "scanned_at": datetime.now(timezone.utc).isoformat(),
            }
        partition.update({"complete": True, "split": False})
        persist()
        print(
            f"[PARTITION] {len(candidate_results)}/{len(universe)} "
            f"{' + '.join(required)} + {len(partners)} partner(s): "
            f"{total} listings",
            flush=True,
        )

    for required, partners in jobs:
        scan_partition(tuple(required), list(partners))

    record["complete"] = set(candidate_results) == expected
    if record["complete"]:
        record["scanned_at"] = datetime.now(timezone.utc).isoformat()
    persist()
    return record


def triple_partition_jobs(universe, entries_by_name, l12=False):
    expected = {tuple(sorted(combo)) for combo in universe}
    ordered = list(entries_by_name)
    jobs = []
    if l12:
        prefixes = [name for name in ordered if entries_by_name[name]["side"] == "prefix"]
        suffixes = [name for name in ordered if entries_by_name[name]["side"] == "suffix"]
        for prefix in prefixes:
            for index, suffix in enumerate(suffixes[:-1]):
                partners = [
                    partner for partner in suffixes[index + 1:]
                    if tuple(sorted((prefix, suffix, partner))) in expected
                ]
                if partners:
                    jobs.append(((prefix, suffix), partners))
        return jobs
    for first_index, first in enumerate(ordered[:-2]):
        for second_index in range(first_index + 1, len(ordered) - 1):
            second = ordered[second_index]
            partners = [
                partner for partner in ordered[second_index + 1:]
                if tuple(sorted((first, second, partner))) in expected
            ]
            if partners:
                jobs.append(((first, second), partners))
    return jobs


def scan_candidate_universe(
    cache,
    cache_path,
    key,
    requester,
    league,
    base_query,
    universe,
    entries_by_name,
    rates,
    refresh=False,
    maximum_new_candidates=0,
    effect_stat_id=None,
):
    if refresh:
        cache.pop(key, None)
    record = cache.setdefault(key, {
        "audit_version": AUDIT_VERSION,
        "candidate_results": {},
        "complete": False,
    })
    results = record.setdefault("candidate_results", {})
    expected_keys = [combo_key(combo) for combo in universe]
    if any(candidate not in expected_keys for candidate in results):
        results.clear()

    scanned_now = 0
    for index, combo in enumerate(universe, 1):
        candidate_key = combo_key(combo)
        if candidate_key in results:
            continue
        if maximum_new_candidates and scanned_now >= maximum_new_candidates:
            break
        query = exact_candidate_query(
            base_query,
            combo,
            entries_by_name,
            effect_stat_id=effect_stat_id,
        )
        result = fetch_exact_candidate(requester, league, query, rates)
        results[candidate_key] = result
        scanned_now += 1
        record.update({
            "candidate_count": len(universe),
            "candidates_scanned": len(results),
            "complete": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        cache[key] = record
        write_json(cache_path, cache)
        print(
            f"[SCAN] {len(results)}/{len(universe)} {candidate_key}: "
            f"{result['total']} listings",
            flush=True,
        )

    record["candidate_count"] = len(universe)
    record["candidates_scanned"] = len(results)
    record["complete"] = set(results) == set(expected_keys)
    if record["complete"]:
        record["scanned_at"] = datetime.now(timezone.utc).isoformat()
    cache[key] = record
    write_json(cache_path, cache)
    return record


def price_candidate_results(record, minimum_chaos, minimum_listings):
    accepted = []
    for candidate_key, result in record.get("candidate_results", {}).items():
        prices = sorted(float(value) for value in result.get("prices", []))
        if int(result.get("total", 0)) < minimum_listings or not prices:
            continue
        if prices[0] < minimum_chaos:
            continue
        accepted.append((
            tuple(candidate_key.split("|")),
            {
                "min_chaos": round(prices[0], 2),
                "max_chaos": round(prices[-1], 2),
                "avg_chaos": round(sum(prices) / len(prices), 2),
                "listings": int(result.get("total", 0)),
                "sample_size": len(prices),
                "trade_url": result.get("trade_url", ""),
                "scanned_at": result.get("scanned_at", ""),
            },
        ))
    accepted.sort(key=lambda row: (-row[1]["min_chaos"], row[0]))
    return accepted


def price_groups(record, minimum_chaos, minimum_listings):
    accepted = []
    for combo_key, group in record.get("groups", {}).items():
        prices = sorted(float(value) for value in group.get("prices", []))
        if len(prices) < minimum_listings or not prices:
            continue
        if prices[0] < minimum_chaos:
            continue
        accepted.append((
            tuple(combo_key.split("|")),
            {
                "min_chaos": round(prices[0], 2),
                "max_chaos": round(prices[min(9, len(prices) - 1)], 2),
                "avg_chaos": round(sum(prices[:10]) / min(10, len(prices)), 2),
                "listings": len(prices),
                "sample_size": min(10, len(prices)),
                "trade_url": record.get("trade_url", ""),
                "scanned_at": record.get("scanned_at", ""),
            },
        ))
    accepted.sort(key=lambda row: (-row[1]["min_chaos"], row[0]))
    return accepted


def notable_mod(pool, name):
    notable = next(n for n in pool["notables"] if n["notableName"] == name)
    side = "S" if notable.get("side") == "suffix" else "P"
    return f"[{side}][1] 1 Added Passive Skill is {name}"


def stat_mod(entry):
    side = "P" if entry["side"] == "prefix" else "S"
    return f"[{side}][1] {entry['text']}({entry['min']})"


def update_template(
    path,
    data,
    metadata,
    pool,
    accepted,
    universe_count,
    universe_hash,
    record,
    minimum_chaos,
    minimum_listings,
    divine_chaos,
    l12_entries=None,
):
    accepted = list(accepted)
    accepted_names = {tuple(sorted(combo)) for combo, _price in accepted}
    for pinned in data.get("pinned_notable_combinations", []):
        pinned_combo = tuple(sorted(str(name) for name in pinned))
        if pinned_combo and pinned_combo not in accepted_names:
            accepted.append((pinned_combo, None))
            accepted_names.add(pinned_combo)
    combos = {}
    prices = {}
    for index, (combo, price) in enumerate(accepted, 1):
        key = str(index)
        if l12_entries is None:
            combos[key] = [notable_mod(pool, name) for name in combo]
        else:
            combos[key] = [
                "[P][1] Added Small Passive Skills have #% increased Effect(35)"
            ] + [stat_mod(l12_entries[name]) for name in combo]
        if price is not None:
            prices[key] = price

    all_mods = []
    for combo in combos.values():
        for mod in combo:
            if mod not in all_mods:
                all_mods.append(mod)
    data["comb_craft_data"] = combos
    data["combo_prices"] = prices
    data["stop_on_two_match"] = [
        combo for combo in combos.values() if len(combo) == 2
    ]
    data["solo_regal_mods"] = all_mods
    price_meta = data.setdefault("price_meta", {})
    price_meta.update({
        "league": metadata["league"],
        "scanned_at": record.get("scanned_at", ""),
        "currency": "chaos",
        "range_basis": "complete priced securable result set",
        "market_scan_complete": True,
        "minimum_chaos": round(minimum_chaos, 2),
        "minimum_popularity": minimum_listings,
        "trade_url": "",
        "candidate_universe_count": universe_count,
        "candidate_universe_sha256": universe_hash,
        "market_results_total": sum(
            int(value.get("total", 0))
            for value in record.get("candidate_results", {}).values()
        ),
        "market_results_fetched": sum(
            len(value.get("prices", []))
            for value in record.get("candidate_results", {}).values()
        ),
        "candidates_scanned": int(record.get("candidates_scanned", 0)),
        "audit_version": AUDIT_VERSION,
        "pinned_combinations": len(data.get("pinned_notable_combinations", [])),
    })
    if divine_chaos:
        price_meta["divine_chaos"] = round(divine_chaos, 2)
    write_json(path, data)


def template_metadata(path, data, league):
    meta = data.get("cluster_meta") or {}
    passive_count = int(meta.get("passive_count", 0))
    name_level = re.search(r"ilvl(\d+)", path.name, flags=re.I)
    minimum_level = int(
        meta.get("minimum_item_level")
        or (name_level.group(1) if name_level else 1)
    )
    return {
        "base": str(meta.get("base", "")).strip(),
        "passive_count": passive_count,
        "minimum_item_level": minimum_level,
        "league": league,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--refresh-poedb", action="store_true")
    parser.add_argument("--template", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-new-candidates", type=int, default=0)
    parser.add_argument("--passives", type=int, choices=(5, 8, 12))
    args = parser.parse_args()

    stats = scanner.load_or_fetch_stats()
    league = scanner.get_current_challenge_league_id()
    rates = scanner.get_currency_rates_chaos(league)
    divine_chaos = float(rates.get("divine") or 0.0)
    large_pools = scanner.load_clusters_with_ids()
    medium_pools = load_medium_pools(stats, refresh=args.refresh_poedb)
    stat_entries = {
        entry["name"]: entry
        for entry in (
            {
                "name": name,
                "id": stat_id,
                "min": minimum,
                "side": side,
                "text": text,
            }
            for name, stat_id, minimum, side, text in scanner.SMALL_PASSIVE_STATS
        )
    }
    requester = scanner.RateLimitedRequester(scanner.UA, {}, {})
    cache_path = ROOT / "data" / f"cluster_template_audit_{league}.json"
    cache = read_json(cache_path)

    paths = sorted((ROOT / "itemcraft").glob("*.json"))
    if args.template:
        wanted = {name.casefold() for name in args.template}
        paths = [path for path in paths if path.stem.casefold() in wanted]
    audited = 0
    for path in paths:
        data = read_json(path)
        meta = data.get("cluster_meta") or {}
        passive_count = int(meta.get("passive_count", 0))
        if passive_count not in (5, 8, 12):
            continue
        if args.passives and passive_count != args.passives:
            continue
        metadata = template_metadata(path, data, league)
        if passive_count == 5:
            pool = find_pool(medium_pools, metadata["base"])
            universe = enumerate_notable_combinations(
                pool["notables"], 2, metadata["minimum_item_level"]
            )
            query = notable_query(metadata, stats, pool["notables"], 2)
            extractor = lambda item, p=pool: extract_notable_combo(
                item,
                {n["notableName"] for n in p["notables"]},
                2,
            )
            minimum_chaos = float(meta.get("minimum_chaos", 40.0))
            minimum_listings = 1
            l12 = None
            entries_by_name = {
                notable["notableName"]: notable for notable in pool["notables"]
            }
            effect_stat_id = None
        elif passive_count == 8:
            pool = find_pool(
                {canonical_text(p["clusterName"]): p for p in large_pools},
                metadata["base"],
            )
            universe = enumerate_notable_combinations(
                pool["notables"], 3, metadata["minimum_item_level"]
            )
            query = notable_query(metadata, stats, pool["notables"], 3)
            extractor = lambda item, p=pool: extract_notable_combo(
                item,
                {n["notableName"] for n in p["notables"]},
                3,
            )
            minimum_divine = float(
                (data.get("price_meta") or {}).get("minimum_divine")
                or DEFAULT_LARGE_MINIMUM_DIVINE
            )
            minimum_chaos = minimum_divine * divine_chaos
            minimum_listings = int(
                (data.get("price_meta") or {}).get("minimum_popularity")
                or DEFAULT_LARGE_MINIMUM_LISTINGS
            )
            l12 = None
            entries_by_name = {
                notable["notableName"]: notable for notable in pool["notables"]
            }
            effect_stat_id = None
        else:
            pool = None
            # Effect is one prefix, so the remaining three targets must be
            # one prefix and two suffixes on a four-affix rare jewel.
            universe = [
                tuple(sorted(combo))
                for combo in itertools.combinations(stat_entries, 3)
                if sum(stat_entries[name]["side"] == "prefix" for name in combo) == 1
                and sum(stat_entries[name]["side"] == "suffix" for name in combo) == 2
            ]
            query = l12_query(metadata, stats, stat_entries)
            extractor = lambda item: extract_l12_combo(item, stat_entries)
            minimum_divine = float(
                (data.get("price_meta") or {}).get("minimum_divine")
                or DEFAULT_LARGE_MINIMUM_DIVINE
            )
            minimum_chaos = minimum_divine * divine_chaos
            minimum_listings = int(
                (data.get("price_meta") or {}).get("minimum_popularity")
                or DEFAULT_LARGE_MINIMUM_LISTINGS
            )
            l12 = stat_entries
            entries_by_name = stat_entries
            effect_stat_id = scanner.find_effect_stat_id(stats)

        universe_set = set(universe)
        universe_digest = combo_hash(universe)
        key = (
            f"AUDIT{AUDIT_VERSION}|{league}|{path.stem}|"
            f"{universe_digest[:16]}"
        )
        print(
            f"[AUDIT] {path.name}: {len(universe)} valid candidates",
            flush=True,
        )
        if passive_count == 5 and not args.max_new_candidates:
            record = scan_medium_candidate_universe(
                cache,
                cache_path,
                key,
                requester,
                league,
                query,
                universe,
                entries_by_name,
                rates,
                refresh=args.refresh,
            )
        elif passive_count in (8, 12) and not args.max_new_candidates:
            record = scan_grouped_triple_universe(
                cache,
                cache_path,
                key,
                requester,
                league,
                query,
                universe,
                entries_by_name,
                rates,
                triple_partition_jobs(
                    universe,
                    entries_by_name,
                    l12=passive_count == 12,
                ),
                effect_stat_id=effect_stat_id,
                l12=passive_count == 12,
                refresh=args.refresh,
            )
        else:
            record = scan_candidate_universe(
                cache,
                cache_path,
                key,
                requester,
                league,
                query,
                universe,
                entries_by_name,
                rates,
                refresh=args.refresh,
                maximum_new_candidates=max(0, args.max_new_candidates),
                effect_stat_id=effect_stat_id,
            )
        if not record.get("complete"):
            print(
                f"[PAUSE] {path.name}: {record.get('candidates_scanned', 0)}/"
                f"{len(universe)} scanned; template was not changed.",
                flush=True,
            )
            continue
        accepted = price_candidate_results(
            record, minimum_chaos, minimum_listings
        )
        print(
            f"[KEEP] {path.name}: {len(accepted)} combinations",
            flush=True,
        )
        if not args.dry_run:
            update_template(
                path,
                data,
                metadata,
                pool,
                accepted,
                len(universe),
                universe_digest,
                record,
                minimum_chaos,
                minimum_listings,
                divine_chaos,
                l12_entries=l12,
            )
        audited += 1
    print(f"[DONE] {audited} cluster templates audited.", flush=True)


if __name__ == "__main__":
    main()
