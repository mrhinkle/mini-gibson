import unittest
from lookup.find import lookup

class T(unittest.TestCase):
    def test_strip(self):
        rows = [{"id": "ada", "name": "Ada"}]
        self.assertEqual(lookup(rows, " ada ")["name"], "Ada")

    def test_missing(self):
        with self.assertRaises(KeyError):
            lookup([{"id": "ada", "name": "Ada"}], "grace")

    def test_blank(self):
        with self.assertRaises(ValueError):
            lookup([{"id": "ada", "name": "Ada"}], "  ")
