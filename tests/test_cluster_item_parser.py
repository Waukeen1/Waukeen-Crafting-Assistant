import ast
import functools
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cluster_craft.pyw"


def load_parser_namespace():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {
        "RE_ADVANCED_ROLL_RANGE",
        "RE_INTANGIBILITY_METADATA",
        "clean_advanced_explicit_mod_block",
        "is_cluster_notable_mod",
        "_parse_item_text_cached",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id in names for target in targets):
                nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            nodes.append(node)

    namespace = {
        "functools": functools,
        "re": re,
        "log_message": lambda *_args, **_kwargs: None,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def test_intangibility_metadata_does_not_hide_cluster_affixes():
    parser = load_parser_namespace()["_parse_item_text_cached"]
    rarity, mods = parser(
        """Item Class: Cluster Jewels
Rarity: Rare
Spirit Shard
Large Cluster Jewel
--------
Item Level: 83
--------
Intangibility: 17%
--------
Adds 8 Passive Skills
2 Added Passive Skills are Jewel Sockets
Added Small Passive Skills grant: 12% increased Lightning Damage
1 Added Passive Skill is Prismatic Heart
1 Added Passive Skill is Storm Drinker
1 Added Passive Skill is Widespread Destruction
--------
Place into an allocated Large Jewel Socket on the Passive Skill Tree.
"""
    )

    assert rarity == "Rare"
    assert "Intangibility: 17%" not in mods
    assert "1 Added Passive Skill is Prismatic Heart" in mods
    assert "1 Added Passive Skill is Widespread Destruction" in mods


def test_intangibility_is_removed_when_it_shares_an_affix_block():
    cleaner = load_parser_namespace()["clean_advanced_explicit_mod_block"]

    assert cleaner(
        [
            "Intangibility: 17%",
            "1 Added Passive Skill is Repeater",
            "1 Added Passive Skill is Eye to Eye",
        ]
    ) == [
        "1 Added Passive Skill is Repeater",
        "1 Added Passive Skill is Eye to Eye",
    ]


def test_only_actual_cluster_notables_are_counted_as_notables():
    is_notable = load_parser_namespace()["is_cluster_notable_mod"]

    assert is_notable("1 Added Passive Skill is Haemorrhage")
    assert not is_notable("Added Small Passive Skills also grant: +4% to Chaos Resistance")
    assert not is_notable("Added Small Passive Skills also grant: +2 to All Attributes")
