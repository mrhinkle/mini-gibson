import unittest
from csvline.parse import parse_csv_line

class T(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_csv_line("a,b,c"), ["a", "b", "c"])

    def test_quoted_comma(self):
        self.assertEqual(parse_csv_line('a,"b,c",d'), ["a", "b,c", "d"])

    def test_escaped_quote(self):
        self.assertEqual(parse_csv_line('a,"say ""hi""",b'), ["a", 'say "hi"', "b"])
