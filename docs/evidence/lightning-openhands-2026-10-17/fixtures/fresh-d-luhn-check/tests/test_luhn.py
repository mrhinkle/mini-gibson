import unittest

from luhn import luhn_valid


class LuhnTests(unittest.TestCase):
    def test_valid_and_invalid_numbers_with_separators(self):
        self.assertTrue(luhn_valid("79927398713"))
        self.assertTrue(luhn_valid("4539-1488 0343-6467"))
        self.assertFalse(luhn_valid("79927398714"))

    def test_bad_characters_short_inputs_and_non_strings(self):
        for value in ["", "- -", "0", "7992x7398713", "１２", 79927398713]:
            with self.subTest(value=value):
                self.assertFalse(luhn_valid(value))


if __name__ == "__main__":
    unittest.main()
