import unittest
from moneyround.round import round_half_away

class T(unittest.TestCase):
    def test_one_point_two(self):
        self.assertEqual(round_half_away(1.2), 1)

    def test_one_point_five(self):
        self.assertEqual(round_half_away(1.5), 2)
