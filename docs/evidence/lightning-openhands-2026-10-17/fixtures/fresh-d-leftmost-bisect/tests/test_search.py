import unittest

from search import leftmost_index


class SearchTests(unittest.TestCase):
    def test_returns_first_duplicate(self):
        values = [1, 2, 2, 2, 5, 8]
        self.assertEqual(leftmost_index(values, 2), 1)
        self.assertEqual(values, [1, 2, 2, 2, 5, 8])

    def test_boundaries_and_missing_value(self):
        self.assertEqual(leftmost_index([1, 3, 5], 1), 0)
        self.assertEqual(leftmost_index([1, 3, 5], 5), 2)
        self.assertEqual(leftmost_index([1, 3, 5], 4), -1)
        self.assertEqual(leftmost_index([], 4), -1)


if __name__ == "__main__":
    unittest.main()
