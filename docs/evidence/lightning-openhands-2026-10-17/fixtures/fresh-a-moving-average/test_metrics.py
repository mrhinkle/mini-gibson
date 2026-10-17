import unittest

from metrics import moving_average


class MovingAverageTests(unittest.TestCase):
    def test_includes_final_complete_window(self):
        self.assertEqual(moving_average([1, 2, 3, 6], 2), [1.5, 2.5, 4.5])

    def test_window_equal_to_length(self):
        self.assertEqual(moving_average((2, 4, 8), 3), [14 / 3])

    def test_oversized_window_and_empty_input(self):
        self.assertEqual(moving_average([1], 2), [])
        self.assertEqual(moving_average([], 1), [])

    def test_rejects_invalid_windows(self):
        for window in (0, -1, 1.5):
            with self.subTest(window=window), self.assertRaises(ValueError):
                moving_average([1], window)


if __name__ == "__main__":
    unittest.main()
