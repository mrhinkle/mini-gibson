import unittest

from run_length import decode_runs


class RunLengthTests(unittest.TestCase):
    def test_expands_runs_and_preserves_values(self):
        marker = object()
        self.assertEqual(decode_runs([("a", 2), ("b", 1)]), ["a", "a", "b"])
        self.assertIs(decode_runs([(marker, 1)])[0], marker)
        self.assertEqual(decode_runs([]), [])

    def test_counts_must_be_positive_non_boolean_integers(self):
        for count in [0, -2, True, 1.5, "2"]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                decode_runs([("x", count)])


if __name__ == "__main__":
    unittest.main()
