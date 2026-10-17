import unittest

from running_peaks import running_peaks


class RunningPeaksTests(unittest.TestCase):
    def test_all_negative_values(self):
        self.assertEqual(running_peaks([-5, -8, -3, -10]), [-5, -5, -3, -3])

    def test_mixed_and_empty_values(self):
        self.assertEqual(running_peaks([2, 1, 4, 4, 3]), [2, 2, 4, 4, 4])
        self.assertEqual(running_peaks([]), [])


if __name__ == "__main__":
    unittest.main()
