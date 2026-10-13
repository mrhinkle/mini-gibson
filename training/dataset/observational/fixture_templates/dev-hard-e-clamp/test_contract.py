import unittest
from clamps.clamp import clamp

class T(unittest.TestCase):
    def test_ends(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)

    def test_below(self):
        self.assertEqual(clamp(-3, 0, 10), 0)

    def test_reversed(self):
        with self.assertRaises(ValueError):
            clamp(1, 5, 1)
