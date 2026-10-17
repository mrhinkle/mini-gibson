import unittest

from iso_week_labels import iso_week_labels


class IsoWeekLabelTests(unittest.TestCase):
    def test_calendar_year_boundary_uses_iso_year(self):
        self.assertEqual(iso_week_labels(["2021-01-01"]), ["2020-W53-5"])

    def test_regular_week_and_order(self):
        self.assertEqual(
            iso_week_labels(["2021-01-04", "2021-01-10"]),
            ["2021-W01-1", "2021-W01-7"],
        )

    def test_invalid_iso_date_raises(self):
        with self.assertRaises(ValueError):
            iso_week_labels(["2021-02-29"])


if __name__ == "__main__":
    unittest.main()
