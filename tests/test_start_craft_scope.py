import ast
import unittest
from pathlib import Path


class StartCraftScopeTests(unittest.TestCase):
    def test_item_branch_does_not_read_map_mode(self):
        source_path = Path(__file__).resolve().parents[1] / "cluster_craft.pyw"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        start_craft = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "start_craft"
        )
        item_branch = next(
            node
            for node in ast.walk(start_craft)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "is_item"
        )
        map_mode_reads = [
            node
            for statement in item_branch.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "map_mode"
        ]
        self.assertEqual(map_mode_reads, [])


if __name__ == "__main__":
    unittest.main()
