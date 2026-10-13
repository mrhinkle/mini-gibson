import datetime
import unittest
from reports.api import dates

class T(unittest.TestCase):
    def test_seven_dates(self):
        got = dates(datetime.date(2024, 3, 15))
        self.assertEqual(got[0], "2024-03-09")
        self.assertEqual(got[-1], "2024-03-15")
        self.assertEqual(len(got), 7)

    def test_contiguous(self):
        got = dates(datetime.date(2024, 1, 3))
        self.assertEqual(got, ["2023-12-28", "2023-12-29", "2023-12-30", "2023-12-31", "2024-01-01", "2024-01-02", "2024-01-03"])
