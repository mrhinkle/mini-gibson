import unittest

from dependencies import dependency_order


class DependencyTests(unittest.TestCase):
    def test_lexical_ready_order_and_dependency_only_nodes(self):
        graph = {"deploy": ["test", "build"], "test": ["build"], "docs": []}
        self.assertEqual(
            dependency_order(graph),
            ["build", "docs", "test", "deploy"],
        )
        self.assertEqual(graph, {"deploy": ["test", "build"], "test": ["build"], "docs": []})

    def test_cycle_is_rejected(self):
        with self.assertRaises(ValueError):
            dependency_order({"a": ["b"], "b": ["a"]})


if __name__ == "__main__":
    unittest.main()
