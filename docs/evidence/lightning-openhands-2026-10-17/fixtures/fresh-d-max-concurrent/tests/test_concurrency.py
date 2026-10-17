import unittest

from concurrency import max_concurrent


class ConcurrencyTests(unittest.TestCase):
    def test_touching_half_open_intervals_do_not_overlap(self):
        self.assertEqual(max_concurrent([(1, 3), (3, 5), (2, 4)]), 2)
        self.assertEqual(max_concurrent([(1, 2), (2, 3), (3, 4)]), 1)
        self.assertEqual(max_concurrent([]), 0)

    def test_invalid_intervals_are_rejected(self):
        for event in [(2, 2), (4, 1)]:
            with self.subTest(event=event), self.assertRaises(ValueError):
                max_concurrent([event])


if __name__ == "__main__":
    unittest.main()
