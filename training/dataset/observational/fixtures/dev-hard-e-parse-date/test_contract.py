import datetime
import unittest
from dates.parse import parse_date

class T(unittest.TestCase):
    def test_datetime(self):
        self.assertEqual(parse_date("2020-01-02T03:04:05"), datetime.date(2020, 1, 2))

    def test_mdy(self):
        self.assertEqual(parse_date("01/02/2020"), datetime.date(2020, 1, 2))

    def test_bad_iso(self):
        with self.assertRaises(ValueError):
            parse_date("2020-13-01")

    def test_bad_mdy(self):
        with self.assertRaises(ValueError):
            parse_date("13/40/2020")
