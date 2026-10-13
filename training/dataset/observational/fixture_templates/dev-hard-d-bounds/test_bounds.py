import unittest
from bounds.range import in_range

class T(unittest.TestCase):
    def test_low_end(self):
        self.assertTrue(in_range(1, 1, 3))

    def test_high_end(self):
        self.assertTrue(in_range(3, 1, 3))

    def test_mid(self):
        self.assertTrue(in_range(2, 1, 3))

    def test_outside(self):
        self.assertFalse(in_range(0, 1, 3))
        self.assertFalse(in_range(4, 1, 3))

    def test_empty(self):
        self.assertFalse(in_range(5, 10, 0))
        self.assertFalse(in_range(0, 10, 0))
