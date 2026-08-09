import ast
import re
from pathlib import Path


def _load_candidate_function(locations):
    source_path = Path(__file__).parents[1] / "cluster_craft.pyw"
    module = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "get_orb_slot_candidates"
    )
    namespace = {
        "re": re,
        "get_orb_locations_dict": lambda: locations,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace["get_orb_slot_candidates"]


def test_augmentation_can_use_any_configured_shared_backup_location():
    candidates = _load_candidate_function(
        {
            "orb of augmentation": "10,20",
            "orb of augmentation slot 2": "30,40",
            "orb of alteration slot 3": "50,60",
            "orb of alteration slot 4": "30,40",
            "orb of alteration slot 5": "70,80",
        }
    )("Orb of Augmentation")

    assert candidates == [
        (1, "orb of augmentation", (10, 20)),
        (2, "orb of augmentation slot 2", (30, 40)),
        (3, "orb of alteration slot 3", (50, 60)),
        (4, "orb of alteration slot 5", (70, 80)),
    ]


def test_alteration_can_use_augmentation_labeled_backup_location():
    candidates = _load_candidate_function(
        {
            "orb of alteration": "11,21",
            "orb of alteration slot 2": "31,41",
            "orb of augmentation slot 6": "71,81",
        }
    )("Orb of Alteration")

    assert candidates[-1] == (3, "orb of augmentation slot 6", (71, 81))


def test_fast_failover_is_not_limited_to_chain_craft():
    source_path = Path(__file__).parents[1] / "cluster_craft.pyw"
    module = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
    }

    for name in (
        "apply_augmentation_with_failover",
        "apply_alteration_with_failover",
    ):
        function = functions[name]
        chain_guards = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Name) and child.id == "chain_craft"
                for child in ast.walk(node.test)
            )
        ]
        assert chain_guards == []
