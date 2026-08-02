import json
import re
from pathlib import Path
from urllib.parse import quote


TRADE_SEARCH_ENDPOINT = "https://www.pathofexile.com/api/trade/search/{league}"
TRADE_RESULTS_URL = "https://www.pathofexile.com/trade/search/{league}/{query_id}"


def canonical_cluster_text(text):
    text = re.sub(
        r"Added Small Passive Skills grant:\s*",
        "",
        text or "",
        flags=re.I,
    )
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def find_cluster_option_id(stats, cluster_name):
    enchant = next(
        (group for group in stats.get("result", []) if group.get("label") == "Enchant"),
        None,
    )
    if not enchant:
        return None

    target = canonical_cluster_text(cluster_name)
    entries = enchant.get("entries", [])
    for entry in entries:
        entry_id = str(entry.get("id", ""))
        if not entry_id.startswith("enchant.stat_3948993189|"):
            continue
        if canonical_cluster_text(entry.get("text", "")) == target:
            return entry_id

    legacy = next(
        (entry for entry in entries if entry.get("id") == "enchant.stat_3948993189"),
        None,
    )
    options = (legacy.get("option") or {}).get("options", []) if legacy else []
    for option in options:
        if canonical_cluster_text(option.get("text", "")) == target:
            return str(option.get("id", ""))
    return None


def build_cluster_base_filter(cluster_option_id):
    option_id = str(cluster_option_id or "")
    if option_id.startswith("enchant.stat_3948993189|"):
        return {"id": option_id}
    return {
        "id": "enchant.stat_3948993189",
        "value": {"option": option_id},
    }


def minimum_item_level_from_name(template_name, default=1):
    match = re.search(r"(?:^|\s-\s)ilvl(\d+)(?:\s|$)", template_name, flags=re.I)
    return int(match.group(1)) if match else int(default)


def _fallback_cluster_metadata(template_name):
    low = template_name.casefold()
    if low.startswith("effect_spell_damage") or low.startswith("fracsiz spell") or low.startswith("fracsız spell"):
        return "10% increased Spell Damage", 12
    if low.startswith("mana reserv"):
        return "6% increased Mana Reservation Efficiency of Skills", 3
    if low.startswith("chaos_"):
        return "12% increased Chaos Damage", 8
    return "", 0


def item_type_for_passive_count(passive_count):
    passive_count = int(passive_count)
    if passive_count <= 3:
        return "Small Cluster Jewel"
    if passive_count <= 6:
        return "Medium Cluster Jewel"
    return "Large Cluster Jewel"


def passive_count_range(passive_count):
    passive_count = int(passive_count)
    if item_type_for_passive_count(passive_count) == "Medium Cluster Jewel":
        return 4, 5
    return passive_count, passive_count


def template_metadata(template_name, template_data):
    meta = dict(template_data.get("cluster_meta") or {})
    fallback_base, fallback_passives = _fallback_cluster_metadata(template_name)
    base = str(meta.get("base") or fallback_base).strip()
    passive_count = int(meta.get("passive_count") or fallback_passives or 0)
    minimum_item_level = int(
        meta.get("minimum_item_level")
        or minimum_item_level_from_name(template_name)
    )
    if not base or passive_count <= 0:
        raise ValueError(f"Cluster metadata is missing for '{template_name}'.")
    return {
        "base": base,
        "passive_count": passive_count,
        "minimum_item_level": minimum_item_level,
        "item_type": item_type_for_passive_count(passive_count),
        "league": str(
            (template_data.get("price_meta") or {}).get("league") or ""
        ).strip(),
    }


def build_trade_query(metadata, cluster_option_id):
    passive_count = int(metadata["passive_count"])
    passive_min, passive_max = passive_count_range(passive_count)
    return {
        "query": {
            "status": {"option": "securable"},
            "type": metadata["item_type"],
            "stats": [
                {
                    "type": "and",
                    "filters": [
                        build_cluster_base_filter(cluster_option_id),
                        {
                            "id": "enchant.stat_3086156145",
                            "value": {
                                "min": passive_min,
                                "max": passive_max,
                            },
                        },
                    ],
                }
            ],
            "filters": {
                "type_filters": {
                    "filters": {
                        "category": {"option": "jewel.cluster"},
                        "rarity": {"option": "nonunique"},
                    }
                },
                "misc_filters": {
                    "filters": {
                        "ilvl": {"min": int(metadata["minimum_item_level"])},
                        "corrupted": {"option": "false"},
                        "fractured_item": {"option": "false"},
                    }
                },
                "trade_filters": {
                    "filters": {"sale_type": {"option": "priced"}}
                },
            },
        },
        "sort": {"price": "asc"},
    }


def load_stats(stats_path):
    with Path(stats_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def create_trade_search(
    session,
    stats,
    template_name,
    template_data,
    league,
    headers=None,
    timeout=20,
):
    metadata = template_metadata(template_name, template_data)
    option_id = find_cluster_option_id(stats, metadata["base"])
    if not option_id:
        raise ValueError(f"Trade stat was not found for cluster base: {metadata['base']}")

    league = str(league or metadata.get("league") or "").strip()
    if not league:
        raise ValueError("Trade league is missing.")
    payload = build_trade_query(metadata, option_id)
    endpoint = TRADE_SEARCH_ENDPOINT.format(league=quote(league, safe=""))
    response = session.post(
        endpoint,
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    query_id = str(result.get("id") or "").strip()
    if not query_id:
        error = result.get("error")
        raise RuntimeError(f"PoE Trade did not return a search id: {error or result}")
    url = TRADE_RESULTS_URL.format(
        league=quote(league, safe=""),
        query_id=quote(query_id, safe=""),
    )
    return url, metadata, payload
