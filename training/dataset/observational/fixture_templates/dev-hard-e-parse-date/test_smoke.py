import datetime
import unittest
from dates.parse import parse_date

class T(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_date("2020-01-02"), datetime.date(2020, 1, 2))
