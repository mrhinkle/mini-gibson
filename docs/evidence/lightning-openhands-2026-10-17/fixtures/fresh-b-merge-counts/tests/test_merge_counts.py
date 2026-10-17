import unittest

from merge_counts import merge_counts


class MergeCountsTests(unittest.TestCase):
    def test_sums_values_and_omits_zero_totals(self):
        self.assertEqual(
            merge_counts({"open": 3, "closed": 1}, {"open": -3, "new": 2}),
            {"closed": 1, "new": 2},
        )

    def test_does_not_mutate_inputs(self):
        left = {"a": 1}
        right = {"a": 2}
        self.assertEqual(merge_counts(left, right), {"a": 3})
        self.assertEqual(left, {"a": 1})
        self.assertEqual(right, {"a": 2})

    def test_empty_inputs(self):
        self.assertEqual(merge_counts(), {})


if __name__ == "__main__":
    unittest.main()
