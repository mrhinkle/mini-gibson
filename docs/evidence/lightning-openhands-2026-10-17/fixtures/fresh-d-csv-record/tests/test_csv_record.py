import unittest

from csv_record import parse_csv_record


class CsvRecordTests(unittest.TestCase):
    def test_quoted_commas_quotes_and_empty_fields(self):
        self.assertEqual(
            parse_csv_record('alpha,"b,c","say ""hi""",'),
            ["alpha", "b,c", 'say "hi"', ""],
        )
        self.assertEqual(parse_csv_record(""), [])

    def test_multiple_records_and_bad_quotes_are_rejected(self):
        for text in ["a,b\n", "a\rb", '"unterminated']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_csv_record(text)


if __name__ == "__main__":
    unittest.main()
