import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "cluster_craft.pyw"
EFFECT = "[P][1] Added Small Passive Skills have #% increased Effect(35)"
ENERGY_SHIELD = (
    "[P][1] Added Small Passive Skills also grant: +# to Maximum Energy Shield(13)"
)
ALL_ATTRIBUTES = (
    "[S][1] Added Small Passive Skills also grant: +# to All Attributes(6)"
)
INTELLIGENCE = (
    "[S][1] Added Small Passive Skills also grant: +# to Intelligence(12)"
)


def load_function(name, namespace=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    loaded = dict(namespace or {})
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"),
        loaded,
    )
    return loaded[name]


def test_cluster_template_sections_use_metadata_and_legacy_names():
    classifier = load_function("cluster_template_size", {"re": __import__("re")})

    assert classifier("Anything", {"cluster_size": "small"}) == "small"
    assert classifier("Anything", {"cluster_meta": {"passive_count": 5}}) == "medium"
    assert classifier("Anything", {"cluster_meta": {"passive_count": 8}}) == "large"
    assert classifier("M5 - Projectile", {}) == "medium"
    assert classifier("effect_spell_damage", {}) == "large"


def make_stop_helper(potential, typed_mods):
    return load_function(
        "find_small_stop_three_match",
        {
            "mods_with_types": lambda mods: typed_mods,
            "_analyze_item_potential": lambda mods, combos: [potential],
            "_effect35_target_type": lambda target: (
                "prefix" if target.startswith("[P]") else "suffix"
            ),
            "_comb_no_int": lambda value: int(value),
        },
    )


def small_settings(enabled=True):
    return {
        "cluster_size": "small",
        "cluster_small_stop_three": enabled,
        "comb_craft_data": {
            "1": [EFFECT, ENERGY_SHIELD, ALL_ATTRIBUTES, INTELLIGENCE]
        },
    }


def test_small_stop_accepts_three_targets_when_effect_is_missing_but_prefix_open():
    potential = {
        "comb_no": "1",
        "match_count": 3,
        "missing_mods": [EFFECT],
        "junk_mods": [],
    }
    helper = make_stop_helper(
        potential,
        [
            ("energy shield", "prefix"),
            ("all attributes", "suffix"),
            ("intelligence", "suffix"),
        ],
    )

    assert helper(["es", "all", "int"], small_settings()) is potential


def test_small_stop_accepts_missing_effect_when_both_prefixes_are_full():
    potential = {
        "comb_no": "1",
        "match_count": 3,
        "missing_mods": [EFFECT],
        "junk_mods": ["junk prefix"],
    }
    helper = make_stop_helper(
        potential,
        [
            ("energy shield", "prefix"),
            ("junk", "prefix"),
            ("all attributes", "suffix"),
            ("intelligence", "suffix"),
        ],
    )

    assert helper(["es", "junk", "all", "int"], small_settings()) is potential


def test_small_stop_accepts_missing_suffix_when_both_suffixes_are_full():
    potential = {
        "comb_no": "1",
        "match_count": 3,
        "missing_mods": [INTELLIGENCE],
        "junk_mods": ["junk suffix"],
    }
    helper = make_stop_helper(
        potential,
        [
            ("effect", "prefix"),
            ("energy shield", "prefix"),
            ("all attributes", "suffix"),
            ("junk", "suffix"),
        ],
    )

    assert helper(["effect", "es", "all", "junk"], small_settings()) is potential


def test_small_stop_is_disabled_outside_small_section():
    potential = {
        "comb_no": "1",
        "match_count": 3,
        "missing_mods": [EFFECT],
        "junk_mods": [],
    }
    helper = make_stop_helper(
        potential,
        [
            ("energy shield", "prefix"),
            ("all attributes", "suffix"),
            ("intelligence", "suffix"),
        ],
    )
    settings = small_settings()
    settings["cluster_size"] = "medium"

    assert helper(["es", "all", "int"], settings) is None
