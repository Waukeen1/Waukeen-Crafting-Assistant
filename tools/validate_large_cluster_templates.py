import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import generate_large_cluster_templates as generator


AFFIX_PATTERN = re.compile(r"^\[(P|S)\]\[\d+\]\s")


def read_json(path, errors):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path.name}: invalid JSON ({exc})")
        return {}


def parse_timestamp(value, label, errors):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        errors.append(f"{label}: invalid timestamp {value!r}")
        return None


def check_fresh(value, label, max_age_hours, errors):
    parsed = parse_timestamp(value, label, errors)
    if parsed is None:
        return
    age_hours = (
        datetime.now(timezone.utc) - parsed
    ).total_seconds() / 3600
    if age_hours < 0 or age_hours > max_age_hours:
        errors.append(
            f"{label}: scan age {age_hours:.2f}h exceeds "
            f"{max_age_hours:.2f}h"
        )


def affix_sides(mods, label, errors):
    sides = []
    for mod in mods:
        match = AFFIX_PATTERN.match(mod)
        if not match:
            errors.append(f"{label}: malformed affix {mod!r}")
            continue
        sides.append(match.group(1))
    if sides.count("P") > 2 or sides.count("S") > 2:
        errors.append(
            f"{label}: impossible affix layout "
            f"P={sides.count('P')} S={sides.count('S')}"
        )


def expected_l8(definition, cluster, discovery, cache, divine_chaos):
    qualified = []
    for candidate in discovery.get("candidates", []):
        combo = candidate["combo"]
        cache_key = (
            f"MARKET3|L8|{definition['slug']}|"
            f"{'|'.join(combo)}"
        )
        verified = generator.qualify_price_record(
            cache.get(cache_key),
            candidate,
            divine_chaos,
            generator.DEFAULT_MINIMUM_DIVINE,
            generator.DEFAULT_MIN_POPULARITY,
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
    combos = {}
    prices = {}
    for index, (_, combo, verified) in enumerate(qualified, 1):
        key = str(index)
        combos[key] = [
            generator.notable_mod(cluster, name)
            for name in combo
        ]
        prices[key] = verified
    return combos, prices


def expected_l12(definition, discovery, cache, divine_chaos, stats_by_name):
    qualified = []
    for candidate in discovery.get("candidates", []):
        combo = candidate["combo"]
        entries = [stats_by_name[name] for name in combo]
        cache_key = (
            f"MARKET3|L12|{definition['slug']}|"
            f"{'|'.join(combo)}"
        )
        verified = generator.qualify_price_record(
            cache.get(cache_key),
            candidate,
            divine_chaos,
            generator.DEFAULT_MINIMUM_DIVINE,
            generator.DEFAULT_MIN_POPULARITY,
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
    effect_mod = (
        "[P][1] Added Small Passive Skills have "
        "#% increased Effect(35)"
    )
    combos = {}
    prices = {}
    for index, (_, entries, verified) in enumerate(qualified, 1):
        key = str(index)
        combos[key] = [effect_mod] + [
            generator.stat_mod(entry)
            for entry in entries
        ]
        prices[key] = verified
    return combos, prices


def compare_price_records(actual, expected, label, errors):
    fields = (
        "min_chaos",
        "max_chaos",
        "avg_chaos",
        "listings",
        "sample_size",
        "trade_url",
        "scanned_at",
        "min_divine",
        "max_divine",
        "discovery_hits",
        "discovery_sample_size",
    )
    for key in expected:
        for field in fields:
            if actual.get(key, {}).get(field) != expected[key].get(field):
                errors.append(
                    f"{label} #{key}: price field {field!r} "
                    "does not match cache"
                )


def validate_template(
    path,
    data,
    passive_count,
    expected_base,
    expected_combos,
    expected_prices,
    max_age_hours,
    errors,
):
    label = path.stem
    combos = data.get("comb_craft_data", {})
    prices = data.get("combo_prices", {})
    meta = data.get("price_meta", {})
    cluster_meta = data.get("cluster_meta", {})

    if data.get("app_mode") != "cluster":
        errors.append(f"{label}: app_mode is not cluster")
    if data.get("craft_logic") != "Rare (regal)":
        errors.append(f"{label}: unexpected craft_logic")
    if cluster_meta.get("base") != expected_base:
        errors.append(f"{label}: cluster base mismatch")
    if cluster_meta.get("passive_count") != passive_count:
        errors.append(f"{label}: passive_count mismatch")
    if not meta.get("market_scan_complete"):
        errors.append(f"{label}: market scan is not marked complete")
    if float(meta.get("minimum_divine", 0)) != 2.0:
        errors.append(f"{label}: minimum_divine is not 2")
    if int(meta.get("minimum_popularity", 0)) != 3:
        errors.append(f"{label}: minimum_popularity is not 3")
    if float(meta.get("divine_chaos", 0)) <= 0:
        errors.append(f"{label}: invalid divine/chaos rate")
    check_fresh(
        meta.get("scanned_at"),
        f"{label} price_meta",
        max_age_hours,
        errors,
    )

    expected_keys = [str(index) for index in range(1, len(combos) + 1)]
    if list(combos) != expected_keys:
        errors.append(f"{label}: combo keys are not consecutive")
    if set(combos) != set(prices):
        errors.append(f"{label}: combo and price keys differ")
    if combos != expected_combos:
        errors.append(f"{label}: combinations do not match cache")
    compare_price_records(prices, expected_prices, label, errors)

    seen = set()
    union = []
    for key, mods in combos.items():
        combo_label = f"{label} #{key}"
        signature = tuple(mods)
        if signature in seen:
            errors.append(f"{combo_label}: duplicate combination")
        seen.add(signature)
        if len(mods) != (3 if passive_count == 8 else 4):
            errors.append(f"{combo_label}: unexpected mod count")
        if len(mods) != len(set(mods)):
            errors.append(f"{combo_label}: duplicate mod")
        affix_sides(mods, combo_label, errors)
        if passive_count == 8:
            if any("Added Passive Skill is" not in mod for mod in mods):
                errors.append(f"{combo_label}: non-notable L8 mod")
        else:
            effect35 = [
                mod for mod in mods
                if "increased Effect(35)" in mod
            ]
            if len(effect35) != 1:
                errors.append(f"{combo_label}: expected one 35% effect")
            if any("Effect(25)" in mod for mod in mods):
                errors.append(f"{combo_label}: contains unwanted 25% effect")

        record = prices.get(key, {})
        min_chaos = float(record.get("min_chaos", 0))
        max_chaos = float(record.get("max_chaos", 0))
        avg_chaos = float(record.get("avg_chaos", 0))
        min_divine = float(record.get("min_divine", 0))
        max_divine = float(record.get("max_divine", 0))
        if int(record.get("listings", 0)) < 3:
            errors.append(f"{combo_label}: fewer than 3 listings")
        if int(record.get("sample_size", 0)) < 1:
            errors.append(f"{combo_label}: empty price sample")
        if min_divine < 2:
            errors.append(f"{combo_label}: minimum price below 2 divine")
        if not (0 < min_chaos <= avg_chaos <= max_chaos):
            errors.append(f"{combo_label}: invalid chaos price range")
        if not (0 < min_divine <= max_divine):
            errors.append(f"{combo_label}: invalid divine price range")
        if not str(record.get("trade_url", "")).startswith(
            "https://www.pathofexile.com/trade/search/"
        ):
            errors.append(f"{combo_label}: invalid trade URL")
        check_fresh(
            record.get("scanned_at"),
            f"{combo_label} price",
            max_age_hours,
            errors,
        )
        for mod in mods:
            if mod not in union:
                union.append(mod)

    if data.get("solo_regal_mods") != union:
        errors.append(f"{label}: solo_regal_mods is not the combo union")
    if data.get("stop_on_two_match") != []:
        errors.append(f"{label}: unexpected stop_on_two_match")
    if data.get("annul_combs") != []:
        errors.append(f"{label}: unexpected annul_combs")
    if data.get("no_annul_combs") != []:
        errors.append(f"{label}: unexpected no_annul_combs")
    if data.get("no_regal_mods") != []:
        errors.append(f"{label}: unexpected no_regal_mods")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-hours", type=float, default=6.0)
    args = parser.parse_args()
    if args.max_age_hours <= 0:
        parser.error("--max-age-hours must be greater than zero")

    errors = []
    template_paths = sorted((ROOT / "itemcraft").glob("L*.json"))
    expected_names = {
        f"L{passive_count} - {definition['slug']}.json"
        for passive_count in (8, 12)
        for definition in generator.CATALOG
    }
    actual_names = {path.name for path in template_paths}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing:
        errors.append(f"missing templates: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected large-cluster templates: {', '.join(extra)}")

    loaded = {
        path.name: read_json(path, errors)
        for path in template_paths
        if path.name in expected_names
    }
    leagues = {
        data.get("price_meta", {}).get("league")
        for data in loaded.values()
        if data
    }
    if len(leagues) != 1 or None in leagues:
        errors.append(f"templates do not share one league: {sorted(leagues)}")
        league = next((value for value in leagues if value), "unknown")
    else:
        league = next(iter(leagues))

    cache_path = ROOT / "data" / f"large_cluster_prices_{league}.json"
    cache = read_json(cache_path, errors)
    clusters = generator.scanner.load_clusters_with_ids()
    stats_by_name = generator.stat_lookup()
    total_combos = {8: 0, 12: 0}
    nonempty = {8: 0, 12: 0}

    for definition in generator.CATALOG:
        cluster = generator.find_cluster(clusters, definition["match"])
        for passive_count, version in (
            (8, generator.L8_DISCOVERY_CACHE_VERSION),
            (12, generator.L12_DISCOVERY_CACHE_VERSION),
        ):
            name = f"L{passive_count} - {definition['slug']}.json"
            data = loaded.get(name, {})
            divine_chaos = float(
                data.get("price_meta", {}).get("divine_chaos", 0)
            )
            discovery_key = (
                f"DISCOVERY{version}|L{passive_count}|"
                f"{definition['slug']}|"
                f"{generator.DEFAULT_MINIMUM_DIVINE:g}|"
                f"{generator.DEFAULT_MIN_POPULARITY}|"
                f"{generator.DEFAULT_MAX_CANDIDATES}"
            )
            discovery = cache.get(discovery_key)
            if not isinstance(discovery, dict):
                errors.append(f"{name}: missing discovery cache")
                discovery = {}
            else:
                check_fresh(
                    discovery.get("scanned_at"),
                    f"{name} discovery",
                    args.max_age_hours,
                    errors,
                )
                for candidate in discovery.get("candidates", []):
                    combo = candidate.get("combo", [])
                    market_key = (
                        f"MARKET3|L{passive_count}|{definition['slug']}|"
                        f"{'|'.join(combo)}"
                    )
                    market = cache.get(market_key)
                    if not isinstance(market, dict):
                        errors.append(
                            f"{name}: missing exact cache for {combo}"
                        )
                    else:
                        check_fresh(
                            market.get("scanned_at"),
                            f"{name} exact {'|'.join(combo)}",
                            args.max_age_hours,
                            errors,
                        )

            if passive_count == 8:
                expected_combos, expected_prices = expected_l8(
                    definition,
                    cluster,
                    discovery,
                    cache,
                    divine_chaos,
                )
            else:
                expected_combos, expected_prices = expected_l12(
                    definition,
                    discovery,
                    cache,
                    divine_chaos,
                    stats_by_name,
                )
            validate_template(
                ROOT / "itemcraft" / name,
                data,
                passive_count,
                cluster["clusterName"],
                expected_combos,
                expected_prices,
                args.max_age_hours,
                errors,
            )
            total_combos[passive_count] += len(expected_combos)
            if expected_combos:
                nonempty[passive_count] += 1

    leftovers = list(ROOT.rglob("*.tmp"))
    if leftovers:
        errors.append(
            f"temporary files remain: "
            f"{', '.join(str(path.relative_to(ROOT)) for path in leftovers)}"
        )

    if errors:
        print(f"[FAIL] {len(errors)} validation error(s)")
        for error in errors:
            print(f" - {error}")
        raise SystemExit(1)

    print(
        f"[PASS] 34 templates validated for {league}: "
        f"L8={total_combos[8]} combos across {nonempty[8]} bases, "
        f"L12={total_combos[12]} combos across {nonempty[12]} bases."
    )


if __name__ == "__main__":
    main()
