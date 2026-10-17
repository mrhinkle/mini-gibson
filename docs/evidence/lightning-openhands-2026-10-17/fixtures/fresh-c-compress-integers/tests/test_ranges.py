import unittest

from ranges import compress_integers


class CompressIntegersTests(unittest.TestCase):
    def test_mixed_ranges(self):
        self.assertEqual(compress_integers([8, 1, 2, 3, 5, 7]), "1-3,5,7-8")

    def test_duplicates_are_removed(self):
        self.assertEqual(compress_integers([3, 2, 2, 1, 3]), "1-3")

    def test_negative_ranges_and_empty_input(self):
        self.assertEqual(compress_integers([-1, -3, -2, 1]), "-3--1,1")
        self.assertEqual(compress_integers([]), "")

    def test_invalid_values(self):
        for values in [[1, 2.0], [True, 2], ["1"]]:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    compress_integers(values)


if __name__ == "__main__":
    unittest.main()
