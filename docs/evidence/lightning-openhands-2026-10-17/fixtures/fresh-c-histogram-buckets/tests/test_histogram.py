import unittest

from histogram import histogram


class HistogramTests(unittest.TestCase):
    def test_boundary_values_use_lower_bucket(self):
        self.assertEqual(histogram([-1, 0, 1, 10, 11], [0, 10]), [2, 2, 1])

    def test_empty_boundaries_and_generators(self):
        values = (value for value in [1, 2, 3])
        self.assertEqual(histogram(values, []), [3])

    def test_inputs_are_not_mutated(self):
        values = [3, 1, 2]
        boundaries = [1, 2]
        histogram(values, boundaries)
        self.assertEqual(values, [3, 1, 2])
        self.assertEqual(boundaries, [1, 2])

    def test_invalid_boundaries(self):
        for boundaries in [[2, 1], [1, 1], [True], [float("inf")], ["1"]]:
            with self.subTest(boundaries=boundaries):
                with self.assertRaises(ValueError):
                    histogram([0], boundaries)

    def test_invalid_values(self):
        for values in [[True], [float("nan")], ["1"]]:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    histogram(values, [0])


if __name__ == "__main__":
    unittest.main()
