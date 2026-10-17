import unittest

from nested import set_in_copy


class NestedUpdateTests(unittest.TestCase):
    def test_existing_path_without_mutation(self):
        original = {"a": {"b": 1}, "untouched": {"x": 2}}
        result = set_in_copy(original, ["a", "b"], 9)
        self.assertEqual(result, {"a": {"b": 9}, "untouched": {"x": 2}})
        self.assertEqual(original, {"a": {"b": 1}, "untouched": {"x": 2}})

    def test_creates_missing_dictionaries(self):
        self.assertEqual(set_in_copy({}, ["a", "b", "c"], 3), {"a": {"b": {"c": 3}}})

    def test_non_dictionary_conflict(self):
        with self.assertRaises(TypeError):
            set_in_copy({"a": 1}, ["a", "b"], 2)

    def test_invalid_data_and_paths(self):
        for args in [([], ["a"], 1), ({}, [], 1), ({}, None, 1), ({}, 1, 1), ({}, [""], 1), ({}, [1], 1)]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    set_in_copy(*args)


if __name__ == "__main__":
    unittest.main()
