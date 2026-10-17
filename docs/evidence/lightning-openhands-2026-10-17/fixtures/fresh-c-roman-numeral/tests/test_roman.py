import unittest

from roman import parse_roman


class RomanNumeralTests(unittest.TestCase):
    def test_canonical_values(self):
        cases = {"I": 1, "IV": 4, "XLII": 42, "MCMXCIV": 1994, "MMMCMXCIX": 3999}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_roman(text), expected)

    def test_noncanonical_and_out_of_range_forms(self):
        for text in ["IIII", "IL", "VX", "MMMM", "IIV"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_roman(text)

    def test_invalid_types_and_characters(self):
        for value in ["", "iv", "ABC", None, 10]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_roman(value)


if __name__ == "__main__":
    unittest.main()
