import unittest
from measures.cli import cli_main
from measures.units import convert

class T(unittest.TestCase):
    def test_km(self):
        self.assertEqual(convert(2500, "km"), 2.5)

    def test_mi(self):
        self.assertEqual(convert(1600, "mi"), 1)

    def test_cli_mi(self):
        self.assertEqual(cli_main(["1600", "mi"]), 1)

    def test_cli_km(self):
        self.assertEqual(cli_main(["1000", "km"]), 1)

    def test_bad_unit(self):
        with self.assertRaises(ValueError):
            convert(1, "furlong")
