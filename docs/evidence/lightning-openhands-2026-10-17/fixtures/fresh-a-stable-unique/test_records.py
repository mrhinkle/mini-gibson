import unittest

from records import stable_unique_by


class StableUniqueTests(unittest.TestCase):
    def test_keeps_first_duplicate(self):
        rows = [
            {"id": 2, "name": "first two"},
            {"id": 1, "name": "one"},
            {"id": 2, "name": "later two"},
        ]
        self.assertEqual(stable_unique_by(rows, "id"), rows[:2])

    def test_accepts_generator_and_empty_input(self):
        rows = ({"id": value} for value in [3, 3, 4])
        self.assertEqual(stable_unique_by(rows, "id"), [{"id": 3}, {"id": 4}])
        self.assertEqual(stable_unique_by([], "id"), [])

    def test_missing_key_raises(self):
        with self.assertRaises(KeyError):
            stable_unique_by([{"other": 1}], "id")


if __name__ == "__main__":
    unittest.main()
