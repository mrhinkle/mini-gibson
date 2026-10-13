import unittest
from ledger.credit import apply_credit

class T(unittest.TestCase):
    def test_same_key_once(self):
        seen = set()
        b = apply_credit(100, 40, "k1", seen)
        b = apply_credit(b, 40, "k1", seen)
        self.assertEqual(b, 140)

    def test_two_keys(self):
        seen = set()
        b = apply_credit(0, 10, "k1", seen)
        b = apply_credit(b, 10, "k2", seen)
        self.assertEqual(b, 20)

    def test_missing(self):
        with self.assertRaises(ValueError) as ctx:
            apply_credit(0, 10, "", set())
        self.assertEqual(str(ctx.exception), "missing key")
