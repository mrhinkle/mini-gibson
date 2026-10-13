import unittest
from users.store import Directory

class T(unittest.TestCase):
    def test_normalize(self):
        d = Directory()
        self.assertEqual(d.add(" A@B.com "), "a@b.com")

    def test_duplicate(self):
        d = Directory()
        d.add(" A@B.com ")
        with self.assertRaises(ValueError) as ctx:
            d.add("a@b.com")
        self.assertEqual(str(ctx.exception), "duplicate")

    def test_blank(self):
        d = Directory()
        with self.assertRaises(ValueError) as ctx:
            d.add("  ")
        self.assertEqual(str(ctx.exception), "bad email")

    def test_no_at(self):
        d = Directory()
        with self.assertRaises(ValueError) as ctx:
            d.add("not-an-email")
        self.assertEqual(str(ctx.exception), "bad email")
