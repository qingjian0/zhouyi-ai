import ast
from collections import Counter
from pathlib import Path
import unittest


class ZPCMMethodUniquenessTests(unittest.TestCase):
    def test_zpcm_memory_class_has_no_duplicate_method_definitions(self):
        source = Path(__file__).parents[1] / "prototype" / "zpcm_memory.py"
        module = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        classes = [
            node for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "ZPCMMemory"
        ]
        self.assertEqual(len(classes), 1)
        methods = [
            node.name for node in classes[0].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        duplicates = sorted(
            name for name, count in Counter(methods).items() if count > 1
        )
        self.assertEqual(duplicates, [], f"shadowed ZPCMMemory methods: {duplicates}")


if __name__ == "__main__":
    unittest.main()
