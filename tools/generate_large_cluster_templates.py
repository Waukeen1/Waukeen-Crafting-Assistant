import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cluster_arat as scanner


PRICE_CACHE_TTL_SECONDS = 6 * 60 * 60
DEFAULT_MINIMUM_DIVINE = 2.0
DEFAULT_MIN_POPULARITY = 3
DEFAULT_MAX_CANDIDATES = 8
L8_MARKET_SAMPLE_SIZE = 20
L12_MARKET_SAMPLE_SIZE = 10
L8_DISCOVERY_CACHE_VERSION = 4
L12_DISCOVERY_CACHE_VERSION = 5


CATALOG = [
    {
        "slug": "AxeSword",
        "match": "Axe Attacks deal",
        "l8": [
            ["Bloodscent", "Feed the Fury", "Martial Prowess"],
            ["Vicious Skewering", "Wound Aggravation", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "StaffMace",
        "match": "Staff Attacks deal",
        "l8": [
            ["Overlord", "Weight Advantage", "Martial Prowess"],
            ["Overlord", "Feed the Fury", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "ClawDagger",
        "match": "Claw Attacks deal",
        "l8": [
            ["Fan of Blades", "Feed the Fury", "Martial Prowess"],
            ["Fan of Blades", "Fuel the Fight", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "Bow",
        "match": "increased Damage with Bows",
        "l8": [
            ["Broadside", "Tempered Arrowheads", "Martial Prowess"],
            ["Arcing Shot", "Feed the Fury", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "Wand",
        "match": "Wand Attacks deal",
        "l8": [
            ["Opportunistic Fusilade", "Storm's Hand", "Martial Prowess"],
            ["Explosive Force", "Opportunistic Fusilade", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum ES",
    },
    {
        "slug": "TwoHand",
        "match": "increased Damage with Two Handed",
        "l8": [
            ["Martial Mastery", "Brutal Infamy", "Martial Prowess"],
            ["Titanic Swings", "Battlefield Dominator", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "DualWield",
        "match": "increased Attack Damage while Dual Wielding",
        "l8": [
            ["Quick and Deadly", "Deadly Repartee", "Martial Prowess"],
            ["Quick and Deadly", "Feed the Fury", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "Shield",
        "match": "increased Attack Damage while holding a Shield",
        "l8": [
            ["Veteran Defender", "Feed the Fury", "Martial Prowess"],
            ["Strike Leader", "Veteran Defender", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "Attack",
        "match": "10% increased Attack Damage",
        "l8": [
            ["Feed the Fury", "Fuel the Fight", "Martial Prowess"],
            ["Drive the Destruction", "Feed the Fury", "Martial Prowess"],
        ],
        "speed": "Attack Speed",
        "defence": "Maximum Life",
    },
    {
        "slug": "Spell",
        "match": "10% increased Spell Damage",
        "l8": [
            ["Arcane Heroism", "Practiced Caster", "Thaumophage"],
            ["Mage Hunter", "Practiced Caster", "Thaumophage"],
        ],
        "speed": "Cast Speed",
        "defence": "Maximum ES",
    },
    {
        "slug": "Elemental",
        "match": "10% increased Elemental Damage",
        "l8": [
            ["Sadist", "Prismatic Heart", "Doryani's Lesson"],
            ["Corrosive Elements", "Prismatic Heart", "Doryani's Lesson"],
        ],
        "speed": "A&C Speed Elemental",
        "defence": "Maximum ES",
    },
    {
        "slug": "Physical",
        "match": "12% increased Physical Damage",
        "l8": [
            ["Master the Fundamentals", "Battle-Hardened", "Force Multiplier"],
            ["Iron Breaker", "Battle-Hardened", "Force Multiplier"],
        ],
        "speed": "A&C Speed Physical",
        "defence": "Maximum Life",
    },
    {
        "slug": "Fire",
        "match": "12% increased Fire Damage",
        "l8": [
            ["Burning Bright", "Prismatic Heart", "Doryani's Lesson"],
            ["Master of Fire", "Burning Bright", "Doryani's Lesson"],
        ],
        "speed": "A&C Speed Fire",
        "defence": "Maximum ES",
    },
    {
        "slug": "Lightning",
        "match": "12% increased Lightning Damage",
        "l8": [
            ["Scintillating Idea", "Storm Drinker", "Doryani's Lesson"],
            ["Overshock", "Stormrider", "Doryani's Lesson"],
        ],
        "speed": "A&C Speed Lightning",
        "defence": "Maximum ES",
    },
    {
        "slug": "Cold",
        "match": "12% increased Cold Damage",
        "l8": [
            ["Blanketed Snow", "Prismatic Heart", "Doryani's Lesson"],
            ["Cold to the Core", "Blanketed Snow", "Doryani's Lesson"],
        ],
        "speed": "A&C Speed Cold",
        "defence": "Maximum ES",
    },
    {
        "slug": "Chaos",
        "match": "12% increased Chaos Damage",
        "l8": [
            ["Wicked Pall", "Unwaveringly Evil", "Unholy Grace"],
            ["Touch of Cruelty", "Wicked Pall", "Unspeakable Gifts"],
        ],
        "speed": "A&C Speed Chaos",
        "defence": "Maximum Life",
    },
    {
        "slug": "Minion",
        "match": "Minions deal 10% increased Damage",
        "l8": [
            ["Renewal", "Feasting Fiends", "Vicious Bite"],
            ["Renewal", "Rotten Claws", "Vicious Bite"],
        ],
        "speed": "Minions A&C Speed",
        "defence": "Maximum Life",
        "offence": "Maximum Life",
    },
]


def find_cluster(clusters, needle):
    needle = needle.lower()
    return next(c for c in clusters if needle in c["clusterName"].lower())


def notable_mod(cluster, name):
    notable = next(n for n in cluster["notables"] if n["notableName"] == name)
    tag = "S" if notable["side"].lower() == "suffix" else "P"
    return f"[{tag}][1] 1 Added Passive Skill is {name}"


def stat_lookup():
    return {
        name: {
            "name": name,
            "id": stat_id,
            "min": min_value,
            "side": side,
            "text": full_text,
        }
        for name, stat_id, min_value, side, full_text in scanner.SMALL_PASSIVE_STATS
    }


def stat_mod(entry):
    tag = "P" if entry["side"] == "prefix" else "S"
    return f"[{tag}][1] {entry['text']}({entry['min']})"


def read_cache(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def price_record(prices, total, link):
    scanned_at = datetime.now(timezone.utc).isoformat()
    if not prices:
        return {
            "min_chaos": 0.0,
            "max_chaos": 0.0,
            "avg_chaos": 0.0,
            "listings": int(total or 0),
            "sample_size": 0,
            "trade_url": link,
            "scanned_at": scanned_at,
        }
    return {
        "min_chaos": round(min(prices), 2),
        "max_chaos": round(max(prices), 2),
        "avg_chaos": round(sum(prices) / len(prices), 2),
        "listings": int(total or 0),
        "sample_size": len(prices),
        "trade_url": link,
        "scanned_at": scanned_at,
    }


def price_record_is_fresh(record):
    try:
        scanned_at = datetime.fromisoformat(record["scanned_at"])
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - scanned_at.astimezone(timezone.utc)
        return age.total_seconds() < PRICE_CACHE_TTL_SECONDS
    except (KeyError, TypeError, ValueError):
        return False


def price_record_is_usable(record, resume=False):
    if not isinstance(record, dict) or not record.get("scanned_at"):
        return False
    return bool(resume or price_record_is_fresh(record))


def price_meta_timestamp(prices):
    timestamps = [
        record.get("scanned_at")
        for record in prices.values()
        if isinstance(record, dict) and record.get("scanned_at")
    ]
    if timestamps:
        return max(timestamps)
    return "legacy-cache" if prices else "not-scanned"


def query_body(league, requester, body, rates):
    search = requester.send_request(
        f"{scanner.POE_TRADE_BASE}/search/{league}",
        data=body,
    )
    if not search:
        raise RuntimeError("Trade search failed; price cache was not updated.")
    total = int(search.get("total", 0))
    query_id = search.get("id", "")
    link = f"https://www.pathofexile.com/trade/search/{league}/{query_id}"
    ids = search.get("result", [])[:10]
    if not ids:
        return price_record([], total, link)
    fetch_url = (
        f"{scanner.POE_TRADE_BASE}/fetch/{quote(','.join(ids))}"
        f"?query={quote(query_id)}"
    )
    fetched = requester.send_request(fetch_url, is_fetch=True)
    if not fetched:
        raise RuntimeError("Trade fetch failed; price cache was not updated.")
    prices = []
    for result in (fetched or {}).get("result", []):
        try:
            listing_price = result["listing"]["price"]
            currency = listing_price["currency"].lower()
            rate = rates.get(currency)
            if rate is None:
                continue
            chaos = float(listing_price["amount"]) * float(rate)
            if chaos > 0:
                prices.append(chaos)
        except Exception:
            continue
    return price_record(prices, total, link)


def listing_price_chaos(result, rates):
    try:
        listing_price = result["listing"]["price"]
        currency = listing_price["currency"].lower()
        rate = rates.get(currency)
        if rate is None:
            return None
        chaos = float(listing_price["amount"]) * float(rate)
        return chaos if chaos > 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def search_and_fetch_items(league, requester, body, sample_size):
    search = requester.send_request(
        f"{scanner.POE_TRADE_BASE}/search/{league}",
        data=body,
    )
    if not search:
        raise RuntimeError("Market discovery search failed.")
    total = int(search.get("total", 0))
    query_id = search.get("id", "")
    link = f"https://www.pathofexile.com/trade/search/{league}/{query_id}"
    ids = search.get("result", [])[:sample_size]
    results = []
    for start in range(0, len(ids), 10):
        batch = ids[start:start + 10]
        fetch_url = (
            f"{scanner.POE_TRADE_BASE}/fetch/{quote(','.join(batch))}"
            f"?query={quote(query_id)}"
        )
        fetched = requester.send_request(fetch_url, is_fetch=True)
        if not fetched:
            raise RuntimeError("Market discovery fetch failed.")
        results.extend(fetched.get("result", []))
    return results, total, link


def market_discovery_record(candidates, total, link, sample_size):
    return {
        "candidates": candidates,
        "listings": int(total or 0),
        "sample_size": sample_size,
        "trade_url": link,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


def candidate_sort_key(candidate):
    return (
        -int(candidate.get("discovery_hits", 0)),
        -float(candidate.get("sample_min_chaos", 0.0)),
        tuple(candidate.get("combo", [])),
    )


def build_market_price_filter(minimum_divine):
    return {
        "min": float(minimum_divine),
        "option": "divine",
    }


def discover_l8_candidates(
    league,
    requester,
    rates,
    stats,
    cluster,
    minimum_divine,
    min_popularity,
    max_candidates,
):
    option_id = scanner.find_cluster_option_id(stats, cluster["clusterName"])
    body = {
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
                            "value": {"min": 8, "max": 8},
                        },
                    ],
                },
                {
                    "type": "count",
                    "value": {"min": 3},
                    "filters": [
                        {"id": notable["notableId"]}
                        for notable in cluster["notables"]
                    ],
                },
            ],
            "filters": {
                "type_filters": {
                    "filters": {"rarity": {"option": "nonunique"}}
                },
                "trade_filters": {
                    "filters": {
                        "sale_type": {"option": "priced"},
                        "price": build_market_price_filter(minimum_divine),
                    }
                },
            },
        },
        "sort": {"indexed": "desc"},
    }
    results, total, link = search_and_fetch_items(
        league,
        requester,
        body,
        L8_MARKET_SAMPLE_SIZE,
    )
    notable_names = {
        notable["notableName"]
        for notable in cluster["notables"]
    }
    seen = defaultdict(lambda: {"hits": 0, "prices": []})
    for result in results:
        names = []
        for mod in result.get("item", {}).get("explicitMods", []):
            description = mod.get("description", "")
            if "Added Passive Skill is " not in description:
                continue
            name = description.split("Added Passive Skill is ", 1)[1].strip()
            if name in notable_names:
                names.append(name)
        if len(names) != 3:
            continue
        combo = tuple(sorted(names))
        seen[combo]["hits"] += 1
        chaos = listing_price_chaos(result, rates)
        if chaos is not None:
            seen[combo]["prices"].append(chaos)

    candidates = []
    for combo, sample in seen.items():
        prices = sample["prices"]
        candidates.append({
            "combo": list(combo),
            "discovery_hits": sample["hits"],
            "discovery_sample_size": len(results),
            "sample_min_chaos": round(min(prices), 2) if prices else 0.0,
            "sample_max_chaos": round(max(prices), 2) if prices else 0.0,
        })
    candidates.sort(key=candidate_sort_key)
    return market_discovery_record(
        candidates[:max_candidates],
        total,
        link,
        len(results),
    )


def normalize_trade_stat_hash(raw_hash):
    value = str(raw_hash or "")
    # The same affix can be returned under explicit or fractured domains.
    # Discovery must group both forms as the same target stat.
    for prefix in (
        "stat.explicit.",
        "stat.fractured.",
        "explicit.",
        "fractured.",
    ):
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


def discover_l12_candidates(
    league,
    requester,
    rates,
    stats,
    cluster,
    stat_entries,
    minimum_divine,
    min_popularity,
    max_candidates,
):
    option_id = scanner.find_cluster_option_id(stats, cluster["clusterName"])
    body = {
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
                    "filters": [
                        {
                            "id": scanner.find_effect_stat_id(stats),
                            "value": {"min": 35},
                        }
                    ],
                },
                {
                    "type": "count",
                    "value": {"min": 3},
                    "filters": [
                        {
                            "id": entry["id"],
                            "value": {"min": entry["min"]},
                        }
                        for entry in stat_entries.values()
                    ],
                },
            ],
            "filters": {
                "type_filters": {
                    "filters": {"category": {"option": "jewel.cluster"}}
                },
                "misc_filters": {"filters": {"ilvl": {"min": 84}}},
                "trade_filters": {
                    "filters": {
                        "sale_type": {"option": "priced"},
                        "price": build_market_price_filter(minimum_divine),
                    }
                },
            },
        },
        "sort": {"indexed": "desc"},
    }
    results, total, link = search_and_fetch_items(
        league,
        requester,
        body,
        L12_MARKET_SAMPLE_SIZE,
    )
    entries_by_id = {
        normalize_trade_stat_hash(entry["id"]): entry
        for entry in stat_entries.values()
    }
    seen = defaultdict(lambda: {"hits": 0, "prices": []})
    for result in results:
        names = []
        for mod in result.get("item", {}).get("explicitMods", []):
            entry = entries_by_id.get(
                normalize_trade_stat_hash(mod.get("hash"))
            )
            if not entry:
                continue
            value = explicit_mod_value(mod)
            if value is None or value < entry["min"]:
                continue
            names.append(entry["name"])
        if len(names) != 3:
            continue
        combo = tuple(sorted(names))
        seen[combo]["hits"] += 1
        chaos = listing_price_chaos(result, rates)
        if chaos is not None:
            seen[combo]["prices"].append(chaos)

    candidates = []
    for combo, sample in seen.items():
        prices = sample["prices"]
        candidates.append({
            "combo": list(combo),
            "discovery_hits": sample["hits"],
            "discovery_sample_size": len(results),
            "sample_min_chaos": round(min(prices), 2) if prices else 0.0,
            "sample_max_chaos": round(max(prices), 2) if prices else 0.0,
        })
    candidates.sort(key=candidate_sort_key)
    return market_discovery_record(
        candidates[:max_candidates],
        total,
        link,
        len(results),
    )


def query_l8(league, requester, rates, stats, clusters, cluster, combo):
    option_id = scanner.find_cluster_option_id(stats, cluster["clusterName"])
    notable_ids = scanner.resolve_notable_ids_from_file(
        clusters,
        cluster["clusterName"],
        combo,
    )
    filters = [{"id": notable_id} for notable_id in notable_ids]
    filters.extend(
        [
            scanner.build_cluster_base_filter(option_id),
            {
                "id": "enchant.stat_3086156145",
                "value": {"min": 8, "max": 8},
            },
        ]
    )
    body = {
        "query": {
            "status": {"option": "securable"},
            "type": "Large Cluster Jewel",
            "stats": [{"type": "and", "filters": filters}],
            "filters": {
                "type_filters": {"filters": {"rarity": {"option": "nonunique"}}},
                "trade_filters": {"filters": {"sale_type": {"option": "priced"}}},
            },
        },
        "sort": {"price": "asc"},
    }
    return query_body(league, requester, body, rates)


def query_l12(league, requester, rates, stats, cluster, entries):
    option_id = scanner.find_cluster_option_id(stats, cluster["clusterName"])
    stat_groups = [
        {
            "type": "and",
            "filters": [
                {
                    "id": scanner.find_effect_stat_id(stats),
                    "value": {"min": 35},
                }
            ],
        },
        {
            "type": "and",
            "filters": [
                {
                    "id": "enchant.stat_3086156145",
                    "value": {"min": 12, "max": 12},
                },
                scanner.build_cluster_base_filter(option_id),
            ],
        },
    ]
    for entry in entries:
        stat_groups.append(
            {
                "type": "and",
                "filters": [
                    {
                        "id": entry["id"],
                        "value": {"min": entry["min"]},
                    }
                ],
            }
        )
    body = {
        "query": {
            "status": {"option": "securable"},
            "type": "Large Cluster Jewel",
            "stats": stat_groups,
            "filters": {
                "type_filters": {
                    "filters": {"category": {"option": "jewel.cluster"}}
                },
                "misc_filters": {"filters": {"ilvl": {"min": 84}}},
                "trade_filters": {"filters": {"sale_type": {"option": "priced"}}},
            },
        },
        "sort": {"price": "asc"},
    }
    return query_body(league, requester, body, rates)


def qualify_price_record(
    record,
    candidate,
    divine_chaos,
    minimum_divine,
    min_popularity,
):
    if not isinstance(record, dict):
        return None
    try:
        min_chaos = float(record.get("min_chaos", 0.0))
        listings = int(record.get("listings", 0))
        sample_size = int(record.get("sample_size", 0))
    except (TypeError, ValueError):
        return None
    if (
        sample_size <= 0
        or listings < min_popularity
        or min_chaos < minimum_divine * divine_chaos
    ):
        return None
    result = dict(record)
    result.update({
        "min_divine": round(min_chaos / divine_chaos, 2),
        "max_divine": round(
            float(record.get("max_chaos", min_chaos)) / divine_chaos,
            2,
        ),
        "discovery_hits": int(candidate.get("discovery_hits", 0)),
        "discovery_sample_size": int(
            candidate.get("discovery_sample_size", L8_MARKET_SAMPLE_SIZE)
        ),
    })
    return result


def discovery_record_is_usable(record, resume=False):
    return (
        isinstance(record, dict)
        and isinstance(record.get("candidates"), list)
        and price_record_is_usable(record, resume)
    )


def scan_timestamp(discovery, prices):
    timestamps = [
        discovery.get("scanned_at")
        if isinstance(discovery, dict)
        else None,
        price_meta_timestamp(prices),
    ]
    valid = [value for value in timestamps if value and value != "not-scanned"]
    return max(valid) if valid else "not-scanned"


def base_template(
    cluster_name,
    passive_count,
    combos,
    prices,
    league,
    scanned_at,
    minimum_divine,
    divine_chaos,
    min_popularity,
    market_sample_size,
):
    all_mods = []
    for combo in combos.values():
        for mod in combo:
            if mod not in all_mods:
                all_mods.append(mod)
    return {
        "app_mode": "cluster",
        "craft_logic": "Rare (regal)",
        "augment_mode": "Always use",
        "use_exalt": True,
        "use_annul": True,
        "chain_craft": False,
        "chain_count": 1,
        "cluster_meta": {
            "base": cluster_name,
            "passive_count": passive_count,
            "source": "PoEDB + official trade API",
        },
        "comb_craft_data": combos,
        "combo_prices": prices,
        "price_meta": {
            "league": league,
            "scanned_at": scanned_at,
            "currency": "chaos",
            "range_basis": "first 10 cheapest listings",
            "market_scan_complete": True,
            "minimum_divine": minimum_divine,
            "divine_chaos": round(divine_chaos, 2),
            "minimum_popularity": min_popularity,
            "popularity_basis": (
                f"at least {min_popularity} priced online listings; "
                f"candidate discovered in the latest {market_sample_size} "
                f"listings priced at {minimum_divine:g}+ Divine"
            ),
        },
        "stop_on_two_match": [],
        "annul_combs": [],
        "no_annul_combs": [],
        "solo_regal_mods": all_mods,
        "no_regal_mods": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse valid stale checkpoints while completing an interrupted scan.",
    )
    parser.add_argument("--slug", help="Generate only one catalog entry.")
    parser.add_argument("--passives", type=int, choices=(8, 12))
    parser.add_argument(
        "--min-divine",
        type=float,
        default=DEFAULT_MINIMUM_DIVINE,
    )
    parser.add_argument(
        "--min-popularity",
        type=int,
        default=DEFAULT_MIN_POPULARITY,
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
    )
    args = parser.parse_args()
    if args.min_divine <= 0:
        parser.error("--min-divine must be greater than zero.")
    if args.min_popularity < 1:
        parser.error("--min-popularity must be at least one.")
    if args.max_candidates < 1:
        parser.error("--max-candidates must be at least one.")

    clusters = scanner.load_clusters_with_ids()
    stats = scanner.load_or_fetch_stats()
    league = scanner.get_current_challenge_league_id()
    rates = scanner.get_currency_rates_chaos(league)
    divine_chaos = rates.get("divine")
    if not divine_chaos:
        raise RuntimeError("Divine/Chaos rate could not be resolved.")
    requester = scanner.RateLimitedRequester(
        headers=scanner.UA,
        cookies={},
        proxies={},
    )
    stats_by_name = stat_lookup()
    cache_path = ROOT / "data" / f"large_cluster_prices_{league}.json"
    cache = read_cache(cache_path)
    output_dir = ROOT / "itemcraft"
    definitions = CATALOG
    if args.slug:
        definitions = [
            definition
            for definition in CATALOG
            if definition["slug"].lower() == args.slug.lower()
        ]
        if not definitions:
            parser.error(f"Unknown cluster slug: {args.slug}")

    generated_count = 0
    for definition in definitions:
        cluster = find_cluster(clusters, definition["match"])

        if args.passives in (None, 8):
            discovery_key = (
                f"DISCOVERY{L8_DISCOVERY_CACHE_VERSION}|L8|{definition['slug']}|"
                f"{args.min_divine:g}|{args.min_popularity}|"
                f"{args.max_candidates}"
            )
            discovery = cache.get(discovery_key)
            if (
                not discovery_record_is_usable(discovery, args.resume)
                and not args.skip_prices
            ):
                print(f"[DISCOVERY] {discovery_key}", flush=True)
                discovery = discover_l8_candidates(
                    league,
                    requester,
                    rates,
                    stats,
                    cluster,
                    args.min_divine,
                    args.min_popularity,
                    args.max_candidates,
                )
                cache[discovery_key] = discovery
                write_json(cache_path, cache)

            qualified = []
            for candidate in (discovery or {}).get("candidates", []):
                combo = candidate["combo"]
                cache_key = (
                    f"MARKET3|L8|{definition['slug']}|"
                    f"{'|'.join(combo)}"
                )
                needs_scan = (
                    cache_key not in cache
                    or not price_record_is_usable(
                        cache[cache_key],
                        args.resume,
                    )
                )
                if needs_scan and not args.skip_prices:
                    print(f"[VERIFY] {cache_key}", flush=True)
                    cache[cache_key] = query_l8(
                        league,
                        requester,
                        rates,
                        stats,
                        clusters,
                        cluster,
                        combo,
                    )
                    write_json(cache_path, cache)
                verified = qualify_price_record(
                    cache.get(cache_key),
                    candidate,
                    divine_chaos,
                    args.min_divine,
                    args.min_popularity,
                )
                if verified:
                    qualified.append((candidate, combo, verified))
            qualified.sort(
                key=lambda row: (
                    -row[0].get("discovery_hits", 0),
                    -row[2].get("min_chaos", 0),
                    tuple(row[1]),
                )
            )
            l8_combos = {}
            l8_prices = {}
            for index, (_, combo, verified) in enumerate(qualified, 1):
                key = str(index)
                l8_combos[key] = [notable_mod(cluster, name) for name in combo]
                l8_prices[key] = verified

            l8_template = base_template(
                cluster["clusterName"],
                8,
                l8_combos,
                l8_prices,
                league,
                scan_timestamp(discovery or {}, l8_prices),
                args.min_divine,
                divine_chaos,
                args.min_popularity,
                int((discovery or {}).get("sample_size", L8_MARKET_SAMPLE_SIZE)),
            )
            write_json(
                output_dir / f"L8 - {definition['slug']}.json",
                l8_template,
            )
            generated_count += 1

        if args.passives in (None, 12):
            discovery_key = (
                f"DISCOVERY{L12_DISCOVERY_CACHE_VERSION}|L12|{definition['slug']}|"
                f"{args.min_divine:g}|{args.min_popularity}|"
                f"{args.max_candidates}"
            )
            discovery = cache.get(discovery_key)
            if (
                not discovery_record_is_usable(discovery, args.resume)
                and not args.skip_prices
            ):
                print(f"[DISCOVERY] {discovery_key}", flush=True)
                discovery = discover_l12_candidates(
                    league,
                    requester,
                    rates,
                    stats,
                    cluster,
                    stats_by_name,
                    args.min_divine,
                    args.min_popularity,
                    args.max_candidates,
                )
                cache[discovery_key] = discovery
                write_json(cache_path, cache)

            qualified = []
            for candidate in (discovery or {}).get("candidates", []):
                spec = candidate["combo"]
                entries = [stats_by_name[name] for name in spec]
                cache_key = (
                    f"MARKET3|L12|{definition['slug']}|"
                    f"{'|'.join(spec)}"
                )
                needs_scan = (
                    cache_key not in cache
                    or not price_record_is_usable(
                        cache[cache_key],
                        args.resume,
                    )
                )
                if needs_scan and not args.skip_prices:
                    print(f"[VERIFY] {cache_key}", flush=True)
                    cache[cache_key] = query_l12(
                        league,
                        requester,
                        rates,
                        stats,
                        cluster,
                        entries,
                    )
                    write_json(cache_path, cache)
                verified = qualify_price_record(
                    cache.get(cache_key),
                    candidate,
                    divine_chaos,
                    args.min_divine,
                    args.min_popularity,
                )
                if verified:
                    qualified.append((candidate, entries, verified))
            qualified.sort(
                key=lambda row: (
                    -row[0].get("discovery_hits", 0),
                    -row[2].get("min_chaos", 0),
                    tuple(entry["name"] for entry in row[1]),
                )
            )
            l12_combos = {}
            l12_prices = {}
            effect_mod = "[P][1] Added Small Passive Skills have #% increased Effect(35)"
            for index, (_, entries, verified) in enumerate(qualified, 1):
                key = str(index)
                l12_combos[key] = [effect_mod] + [stat_mod(entry) for entry in entries]
                l12_prices[key] = verified

            l12_template = base_template(
                cluster["clusterName"],
                12,
                l12_combos,
                l12_prices,
                league,
                scan_timestamp(discovery or {}, l12_prices),
                args.min_divine,
                divine_chaos,
                args.min_popularity,
                int((discovery or {}).get("sample_size", L12_MARKET_SAMPLE_SIZE)),
            )
            write_json(
                output_dir / f"L12 - {definition['slug']}.json",
                l12_template,
            )
            generated_count += 1

    print(
        f"[DONE] {generated_count} template generated for {league}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
