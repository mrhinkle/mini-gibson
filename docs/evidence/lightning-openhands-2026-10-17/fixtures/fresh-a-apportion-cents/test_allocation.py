import unittest

from allocation import apportion_cents


class ApportionTests(unittest.TestCase):
    def test_preserves_total_with_stable_tie_break(self):
        self.assertEqual(apportion_cents(10, [1, 1, 1]), [4, 3, 3])

    def test_largest_fraction_gets_remainder(self):
        self.assertEqual(apportion_cents(5, [1, 2, 1]), [1, 3, 1])

    def test_zero_total_and_zero_weight(self):
        self.assertEqual(apportion_cents(0, [0, 2]), [0, 0])

    def test_rejects_invalid_inputs(self):
        for total, weights in ((1.5, [1]), (-1, [1]), (1, []), (1, [0, 0]), (1, [1, -1])):
            with self.subTest(total=total, weights=weights), self.assertRaises(ValueError):
                apportion_cents(total, weights)


if __name__ == "__main__":
    unittest.main()
