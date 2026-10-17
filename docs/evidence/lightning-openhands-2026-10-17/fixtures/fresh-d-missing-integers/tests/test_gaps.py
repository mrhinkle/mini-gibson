import unittest

from gaps import missing_integers


class GapTests(unittest.TestCase):
    def test_unsorted_duplicates_and_negative_values(self):
        self.assertEqual(missing_integers([3, -1, 3, 1]), [0, 2])
        self.assertEqual(missing_integers([1, 2, 3]), [])
        self.assertEqual(missing_integers([]), [])
        self.assertEqual(missing_integers([7]), [])

    def test_non_integer_values_are_rejected(self):
        for values in [[1, True, 3], [1, 2.0, 3], ["1", 2]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                missing_integers(values)


if __name__ == "__main__":
    unittest.main()
