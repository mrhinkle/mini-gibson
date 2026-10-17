import unittest

from interleave import round_robin


class InterleaveTests(unittest.TestCase):
    def test_uneven_inputs_continue_and_falsey_values_remain(self):
        self.assertEqual(
            round_robin([1, 2, 3], ["a"], [0, "", "z", "last"]),
            [1, "a", 0, 2, "", 3, "z", "last"],
        )

    def test_generators_and_no_inputs(self):
        self.assertEqual(round_robin((n for n in [1, 2]), (n for n in [3])), [1, 3, 2])
        self.assertEqual(round_robin(), [])


if __name__ == "__main__":
    unittest.main()
