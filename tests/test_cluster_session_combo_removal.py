import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "cluster_craft.pyw"


def load_helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = {"_combo_visible_mods", "_filter_stop_pairs_for_combos"}
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace


def test_deleted_combo_cannot_survive_through_stop_on_two_match():
    helpers = load_helpers()
    effect = "effect35"
    intelligence = "intelligence"
    strength = "strength"
    chaos = "chaos_resistance"
    combos = {
        "1": [effect, intelligence, chaos],
        "2": [effect, strength, chaos],
    }
    pairs = [
        [intelligence, strength],
        [effect, intelligence],
        [effect, strength],
    ]

    filtered = helpers["_filter_stop_pairs_for_combos"](pairs, combos)

    assert [intelligence, strength] not in filtered
    assert [effect, intelligence] in filtered
    assert [effect, strength] in filtered


def test_visible_mods_only_come_from_active_session_combos():
    helpers = load_helpers()
    combos = {"1": ["effect35", "energy_shield"]}

    assert helpers["_combo_visible_mods"](combos) == {
        "effect35",
        "energy_shield",
    }
