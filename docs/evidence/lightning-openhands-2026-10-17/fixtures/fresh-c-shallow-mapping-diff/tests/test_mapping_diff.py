import unittest
from collections import UserDict

from mapping_diff import mapping_diff


class MappingDiffTests(unittest.TestCase):
    def test_all_change_kinds(self):
        before = {"gone": 1, "same": [2], "changed": {"x": 1}}
        after = {"same": [2], "changed": {"x": 2}, "new": 3}
        self.assertEqual(
            mapping_diff(before, after),
            {
                "added": {"new": 3},
                "removed": {"gone": 1},
                "changed": {"changed": ({"x": 1}, {"x": 2})},
            },
        )

    def test_section_keys_are_sorted(self):
        result = mapping_diff({"z": 0, "b": 1}, {"y": 2, "a": 3, "b": 4})
        self.assertEqual(list(result["added"]), ["a", "y"])
        self.assertEqual(list(result["removed"]), ["z"])
        self.assertEqual(list(result["changed"]), ["b"])

    def test_generic_mappings_and_no_mutation(self):
        before = UserDict({"a": 1})
        after = UserDict({"a": 1})
        self.assertEqual(mapping_diff(before, after), {"added": {}, "removed": {}, "changed": {}})
        self.assertEqual(before, {"a": 1})
        self.assertEqual(after, {"a": 1})

    def test_invalid_inputs_and_keys(self):
        for before, after in [([], {}), ({}, []), ({1: "one"}, {}), ({}, {2: "two"})]:
            with self.subTest(before=before, after=after):
                with self.assertRaises(ValueError):
                    mapping_diff(before, after)


if __name__ == "__main__":
    unittest.main()
