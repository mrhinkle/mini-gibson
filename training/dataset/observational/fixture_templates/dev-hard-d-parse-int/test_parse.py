import unittest
from nums import parse_int

class T(unittest.TestCase):
    def test_spaces(self):
        self.assertEqual(parse_int(" 42 "), 42)

    def test_plus(self):
        self.assertEqual(parse_int("+42"), 42)

    def test_negative(self):
        self.assertEqual(parse_int("-7"), -7)

    def test_junk(self):
        with self.assertRaises(ValueError):
            parse_int("42abc")

    def test_empty(self):
        with self.assertRaises(ValueError):
            parse_int("")

    def test_dash_only(self):
        with self.assertRaises(ValueError):
            parse_int("-")
