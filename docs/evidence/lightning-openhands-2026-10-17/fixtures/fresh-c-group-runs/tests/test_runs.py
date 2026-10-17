import unittest

from runs import group_runs


class GroupRunsTests(unittest.TestCase):
    def test_separated_equal_values_are_distinct_runs(self):
        self.assertEqual(group_runs([1, 1, 2, 1]), [(1, 2), (2, 1), (1, 1)])

    def test_generator_and_empty_input(self):
        values = (value for value in ["a", "a", "b"])
        self.assertEqual(group_runs(values), [("a", 2), ("b", 1)])
        self.assertEqual(group_runs([]), [])

    def test_unsortable_unhashable_values(self):
        values = [{"x": 1}, {"x": 1}, [2], {"x": 1}]
        self.assertEqual(group_runs(values), [({"x": 1}, 2), ([2], 1), ({"x": 1}, 1)])


if __name__ == "__main__":
    unittest.main()
