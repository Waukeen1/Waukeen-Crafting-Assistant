import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cluster_craft.pyw"


def load_helper(affix_open=True):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_medium_single_target_exalt_pot"
    )
    namespace = {
        "_pot_affix_state": lambda _pot, _mods: {
            "has_open_slot": affix_open,
        },
    }
    exec(
        compile(ast.Module(body=[helper], type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace["_medium_single_target_exalt_pot"]


def medium_settings(use_exalt=True):
    return {
        "use_exalt": use_exalt,
        "cluster_passive_count": 5,
    }


def test_medium_one_of_two_targets_can_exalt_into_open_affix():
    pot = {
        "match_count": 1,
        "missing_mods": ["[S][1] 1 Added Passive Skill is Flow of Life"],
        "can_spend": True,
    }

    assert load_helper()(["Wasting Affliction", "junk", "junk"], medium_settings(), [pot]) is pot


def test_medium_one_target_does_not_exalt_when_required_affix_side_is_full():
    pot = {
        "match_count": 1,
        "missing_mods": ["[S][1] 1 Added Passive Skill is Flow of Life"],
        "can_spend": True,
    }

    assert load_helper(affix_open=False)([], medium_settings(), [pot]) is None


def test_three_target_combo_and_disabled_exalt_keep_existing_behavior():
    three_target_pot = {
        "match_count": 1,
        "missing_mods": ["[P][1] target one", "[S][1] target two"],
        "can_spend": True,
    }
    two_target_pot = {
        "match_count": 1,
        "missing_mods": ["[S][1] target"],
        "can_spend": True,
    }
    helper = load_helper()

    assert helper([], {"use_exalt": True}, [three_target_pot]) is None
    assert helper([], medium_settings(use_exalt=False), [two_target_pot]) is None


def test_large_cluster_never_uses_medium_single_target_exalt_rule():
    two_target_pot = {
        "match_count": 1,
        "missing_mods": ["[S][1] target"],
        "can_spend": True,
    }

    settings = {"use_exalt": True, "cluster_passive_count": 8}
    assert load_helper()([], settings, [two_target_pot]) is None
