import unittest

from dedupe_records import dedupe_records


class DedupeRecordTests(unittest.TestCase):
    def test_email_comparison_is_trimmed_and_casefolded(self):
        records = [
            {"email": " Ada@Example.com ", "name": "first"},
            {"email": "ada@example.COM", "name": "duplicate"},
            {"email": "bob@example.com", "name": "Bob"},
        ]
        self.assertEqual(dedupe_records(records), [records[0], records[2]])

    def test_returns_copies_without_mutating_input(self):
        records = [{"email": "a@example.com", "tags": ["x"]}]
        result = dedupe_records(records)
        self.assertEqual(result, records)
        self.assertIsNot(result[0], records[0])
        self.assertEqual(records, [{"email": "a@example.com", "tags": ["x"]}])


if __name__ == "__main__":
    unittest.main()
