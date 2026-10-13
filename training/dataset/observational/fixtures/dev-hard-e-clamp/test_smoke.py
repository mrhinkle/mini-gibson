import unittest
from clamps.clamp import clamp

class T(unittest.TestCase):
    def test_mid(self):
        self.assertEqual(clamp(5, 0, 10), 5)
