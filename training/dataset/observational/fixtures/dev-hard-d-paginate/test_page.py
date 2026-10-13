import unittest
from paging.page import page

class T(unittest.TestCase):
    def test_first(self):
        self.assertEqual(page(["a", "b", "c", "d"], 1, 2), ["a", "b"])

    def test_second(self):
        self.assertEqual(page(["a", "b", "c", "d"], 2, 2), ["c", "d"])

    def test_past_end(self):
        self.assertEqual(page(["a", "b", "c", "d"], 3, 2), [])

    def test_size_three(self):
        self.assertEqual(page(["a", "b", "c", "d"], 1, 3), ["a", "b", "c"])

    def test_bad(self):
        with self.assertRaises(ValueError):
            page(["a"], 0, 2)
