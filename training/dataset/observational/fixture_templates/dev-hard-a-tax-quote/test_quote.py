import unittest
from checkout.api import quote

class T(unittest.TestCase):
    def test_half_up_eighth(self):
        got = quote(100, 0.125)
        self.assertEqual(got["tax"], 13)
        self.assertEqual(got["total"], 113)

    def test_half_cent(self):
        self.assertEqual(quote(1, 0.5)["tax"], 1)

    def test_two_and_a_half(self):
        self.assertEqual(quote(5, 0.5)["tax"], 3)
        self.assertEqual(quote(5, 0.5)["total"], 8)

    def test_exact(self):
        got = quote(1000, 0.25)
        self.assertEqual(got["tax"], 250)
        self.assertEqual(got["total"], 1250)
