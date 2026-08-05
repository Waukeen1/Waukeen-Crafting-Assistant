import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "cluster_craft.pyw"


def load_selector(potentials, has_open_slot=False, no_annul=False):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    selector = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_select_best_effect35_progress"
    )
    namespace = {
        "_effect35_potentials": lambda mods, settings, min_match=0: potentials,
        "_effect35_potential_has_open_slot": (
            lambda pot, mods: has_open_slot
        ),
        "_pot_is_no_annul": lambda pot, settings: no_annul,
    }
    exec(
        compile(ast.Module(body=[selector], type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace["_select_best_effect35_progress"]


def test_full_effect35_item_with_two_targets_and_two_junk_uses_annul():
    pot = {
        "comb_no": "3",
        "match_count": 2,
        "missing_mods": ["target-prefix", "target-suffix"],
        "junk_mods": ["junk-prefix", "junk-suffix"],
        "is_perfect_match": False,
    }
    selector = load_selector([pot], has_open_slot=False)

    action, chosen, skipped = selector(
        ["effect35", "dexterity", "low-es", "fire-resistance"],
        {"use_exalt": True, "use_annul": True},
    )

    assert action == "annul"
    assert chosen is pot
    assert skipped == []


def test_two_target_effect35_item_scours_when_annul_is_disabled():
    pot = {
        "comb_no": "3",
        "match_count": 2,
        "missing_mods": ["target-prefix", "target-suffix"],
        "junk_mods": ["junk-prefix", "junk-suffix"],
        "is_perfect_match": False,
    }
    selector = load_selector([pot], has_open_slot=False)

    action, chosen, skipped = selector(
        ["effect35", "dexterity", "low-es", "fire-resistance"],
        {"use_exalt": True, "use_annul": False},
    )

    assert action is None
    assert chosen is None
    assert skipped == []


def test_no_annul_rule_still_blocks_two_target_annul():
    pot = {
        "comb_no": "3",
        "match_count": 2,
        "missing_mods": ["target-prefix", "target-suffix"],
        "junk_mods": ["junk-prefix", "junk-suffix"],
        "is_perfect_match": False,
    }
    selector = load_selector([pot], has_open_slot=False, no_annul=True)

    action, chosen, skipped = selector(
        ["effect35", "dexterity", "low-es", "fire-resistance"],
        {"use_exalt": True, "use_annul": True},
    )

    assert action is None
    assert chosen is None
    assert skipped == ["3"]
