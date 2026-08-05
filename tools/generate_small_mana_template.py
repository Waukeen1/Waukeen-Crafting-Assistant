import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "itemcraft"
    / "S3 - Mana Reservation - ilvl84 - 35 Effect Valuable.json"
)

EFFECT = "[P][1] Added Small Passive Skills have #% increased Effect(35)"
PREFIXES = (
    "[P][1] Added Small Passive Skills also grant: +# to Maximum Energy Shield(13)",
    "[P][1] Added Small Passive Skills also grant: +# to Maximum Life(14)",
    "[P][1] 1 Added Passive Skill is Introspection",
)
ALL_ATTRIBUTES = "[S][1] Added Small Passive Skills also grant: +# to All Attributes(6)"
INTELLIGENCE = "[S][1] Added Small Passive Skills also grant: +# to Intelligence(12)"
STRENGTH = "[S][1] Added Small Passive Skills also grant: +# to Strength(12)"
DEXTERITY = "[S][1] Added Small Passive Skills also grant: +# to Dexterity(12)"
ALL_RESISTANCES = (
    "[S][1] Added Small Passive Skills also grant: +#% to all Elemental Resistances(6)"
)
CHAOS_RESISTANCE = (
    "[S][1] Added Small Passive Skills also grant: +#% to Chaos Resistance(7)"
)

SUFFIX_PAIRS = (
    (ALL_ATTRIBUTES, INTELLIGENCE),
    (ALL_ATTRIBUTES, STRENGTH),
    (ALL_ATTRIBUTES, DEXTERITY),
    (ALL_ATTRIBUTES, ALL_RESISTANCES),
    (ALL_ATTRIBUTES, CHAOS_RESISTANCE),
    (INTELLIGENCE, STRENGTH),
    (INTELLIGENCE, ALL_RESISTANCES),
    (INTELLIGENCE, CHAOS_RESISTANCE),
    (STRENGTH, ALL_RESISTANCES),
    (ALL_RESISTANCES, CHAOS_RESISTANCE),
)


def build_template():
    combinations = {}
    combo_number = 1
    for prefix in PREFIXES:
        for suffix_a, suffix_b in SUFFIX_PAIRS:
            combinations[str(combo_number)] = [
                EFFECT,
                prefix,
                suffix_a,
                suffix_b,
            ]
            combo_number += 1

    return {
        "app_mode": "cluster",
        "cluster_size": "small",
        "craft_logic": "Rare (regal)",
        "augment_mode": "Always use",
        "use_exalt": True,
        "use_annul": True,
        "chain_craft": False,
        "chain_count": 1,
        "cluster_small_stop_three_mods": False,
        "cluster_meta": {
            "base": "6% increased Mana Reservation Efficiency of Skills",
            "passive_count": 3,
            "minimum_item_level": 84,
        },
        "comb_craft_data": combinations,
        "combo_prices": {
            "1": {
                "min_divine": 300.0,
                "max_divine": 300.0,
                "sample_size": 1,
            },
            "11": {
                "min_divine": 85.0,
                "max_divine": 85.0,
                "sample_size": 1,
            },
        },
        "price_meta": {
            "league": "Allflame",
            "scanned_at": "2026-08-04",
            "range_basis": "official trade API, lowest observed listing",
            "market_scan_complete": False,
        },
        "stop_on_two_match": [],
        "annul_combs": [],
        "no_annul_combs": [],
        "solo_regal_mods": [
            EFFECT,
            *PREFIXES,
            ALL_ATTRIBUTES,
            INTELLIGENCE,
            STRENGTH,
            DEXTERITY,
            ALL_RESISTANCES,
            CHAOS_RESISTANCE,
        ],
        "no_regal_mods": [],
    }


def main():
    OUTPUT.write_text(
        json.dumps(build_template(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
