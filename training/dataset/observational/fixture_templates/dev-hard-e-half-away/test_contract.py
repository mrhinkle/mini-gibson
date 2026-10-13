import unittest
from moneyround.round import round_half_away

class T(unittest.TestCase):
    def test_two_point_five(self):
        self.assertEqual(round_half_away(2.5), 3)

    def test_neg_one_point_five(self):
        self.assertEqual(round_half_away(-1.5), -2)

    def test_neg_two_point_five(self):
        self.assertEqual(round_half_away(-2.5), -3)
