import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_integer_seconds(self):
        self.assertEqual(parse_duration("15s"), 15.0)

    def test_decimal_minutes_and_whitespace(self):
        self.assertEqual(parse_duration(" 2.5M "), 150.0)

    def test_milliseconds(self):
        self.assertEqual(parse_duration("250ms"), 0.25)

    def test_rejects_bad_values(self):
        for value in ("-1s", "1 day", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_duration(value)


if __name__ == "__main__":
    unittest.main()
