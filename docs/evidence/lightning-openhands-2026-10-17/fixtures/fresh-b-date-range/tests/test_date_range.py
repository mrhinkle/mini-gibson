import unittest

from date_range import dates_in_window


class DateRangeTests(unittest.TestCase):
    def test_both_boundaries_are_inclusive_and_order_is_preserved(self):
        values = ["2024-03-11", "2024-03-09", "2024-03-10", "2024-03-11"]
        self.assertEqual(
            dates_in_window(values, "2024-03-10", "2024-03-11"),
            ["2024-03-11", "2024-03-10", "2024-03-11"],
        )

    def test_single_day_window_includes_that_day(self):
        self.assertEqual(dates_in_window(["2024-02-29"], "2024-02-29", "2024-02-29"), ["2024-02-29"])

    def test_invalid_range_raises(self):
        with self.assertRaises(ValueError):
            dates_in_window([], "2024-03-12", "2024-03-11")


if __name__ == "__main__":
    unittest.main()
