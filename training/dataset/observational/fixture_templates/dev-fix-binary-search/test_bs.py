import unittest
from bs import binary_search

class T(unittest.TestCase):
    def test_found(self):
        self.assertEqual(binary_search([1, 3, 5, 7, 9], 7), 3)

    def test_missing(self):
        self.assertEqual(binary_search([1, 3, 5], 4), -1)

    def test_one(self):
        self.assertEqual(binary_search([2], 2), 0)

    def test_last(self):
        # catches hi = len(arr) IndexError / wrong bound
        self.assertEqual(binary_search([1, 2, 3, 4, 5], 5), 4)

    def test_first(self):
        self.assertEqual(binary_search([1, 2, 3, 4, 5], 1), 0)

if __name__ == "__main__":
    unittest.main()
