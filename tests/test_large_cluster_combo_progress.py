import ast
import functools
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cluster_craft.pyw"


def load_combo_analyzer():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted_assignments = {
        "RE_TARGET_CONTENT",
        "RE_TRAILING_ROLL",
        "RE_TARGET_SPEND",
        "MATCH_WILDCARD_PATTERN",
    }
    wanted_functions = {
        "_extract_first_numeric_value",
        "_comb_cache_key",
        "_get_compiled_comb_data",
        "_analyze_item_potential_cached",
    }
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in wanted_assignments
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            selected.append(node)
    namespace = {"re": re, "functools": functools}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace


def test_fire_large_keeps_prismatic_and_disorienting_as_valuable_pair():
    template = json.loads(
        (ROOT / "itemcraft" / "L8 - Fire - ilvl75.json").read_text(
            encoding="utf-8"
        )
    )
    namespace = load_combo_analyzer()
    mods = (
        "1 Added Passive Skill is Prismatic Heart",
        "Added Small Passive Skills also grant: Regenerate 0.15% of Life per Second",
        "1 Added Passive Skill is Disorienting Display",
    )
    comb_key = namespace["_comb_cache_key"](template["comb_craft_data"])
    potentials = namespace["_analyze_item_potential_cached"](mods, comb_key)

    assert any(match_count == 2 and can_spend for _, match_count, _, _, _, can_spend in potentials)
