import unittest
from lookup.find import lookup

class T(unittest.TestCase):
    def test_exact(self):
        rows = [{"id": "ada", "name": "Ada"}]
        self.assertEqual(lookup(rows, "ada")["name"], "Ada")
