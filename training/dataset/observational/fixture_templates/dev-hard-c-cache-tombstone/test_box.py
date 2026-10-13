import unittest
from kbox.box import Box

class T(unittest.TestCase):
    def test_missing(self):
        self.assertIsNone(Box().get("a"))

    def test_set_get(self):
        b = Box()
        b.set("a", 1)
        self.assertEqual(b.get("a"), 1)

    def test_invalidate(self):
        b = Box()
        b.set("a", 1)
        b.invalidate("a")
        self.assertIsNone(b.get("a"))

    def test_set_after_invalidate(self):
        b = Box()
        b.set("a", 1)
        b.invalidate("a")
        b.set("a", 2)
        self.assertEqual(b.get("a"), 2)

    def test_neighbor_survives(self):
        b = Box()
        b.set("a", 1)
        b.set("b", 2)
        b.invalidate("a")
        self.assertIsNone(b.get("a"))
        self.assertEqual(b.get("b"), 2)
