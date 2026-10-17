import unittest

from pairs import two_sum_pair


class TwoSumPairTests(unittest.TestCase):
    def test_lexicographic_tie_break(self):
        self.assertEqual(two_sum_pair([1, 2, 3, 4], 5), (0, 3))

    def test_duplicates_and_no_match(self):
        self.assertEqual(two_sum_pair([3, 3, 3], 6), (0, 1))
        self.assertIsNone(two_sum_pair([1, 2], 8))

    def test_one_shot_iterable(self):
        values = (value for value in [8, 1, 7, 2])
        self.assertEqual(two_sum_pair(values, 9), (0, 1))

    def test_invalid_values_and_target(self):
        for values, target in [([1, True], 2), ([1, 2.0], 3), ([1, 2], False), ([1, 2], 3.0)]:
            with self.subTest(values=values, target=target):
                with self.assertRaises(ValueError):
                    two_sum_pair(values, target)


if __name__ == "__main__":
    unittest.main()
