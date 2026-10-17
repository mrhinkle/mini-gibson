import unittest

from flatten import flatten_lists


class FlattenTests(unittest.TestCase):
    def test_nested_lists_are_recursive_but_other_values_are_atomic(self):
        values = [1, [2, [3, []]], (4, 5), "ab", [[6]]]
        self.assertEqual(flatten_lists(values), [1, 2, 3, (4, 5), "ab", 6])
        self.assertEqual(values, [1, [2, [3, []]], (4, 5), "ab", [[6]]])

    def test_empty_list(self):
        self.assertEqual(flatten_lists([]), [])


if __name__ == "__main__":
    unittest.main()
