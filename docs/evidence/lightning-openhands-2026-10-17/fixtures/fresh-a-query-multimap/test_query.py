import unittest

from query import parse_query_multimap


class QueryMultimapTests(unittest.TestCase):
    def test_duplicates_blanks_and_decoding(self):
        query = "?tag=red&tag=blue&empty=&name=Ada+Lovelace&path=a%2Fb"
        self.assertEqual(
            parse_query_multimap(query),
            {
                "tag": ["red", "blue"],
                "empty": [""],
                "name": ["Ada Lovelace"],
                "path": ["a/b"],
            },
        )

    def test_key_without_equals_has_blank_value(self):
        self.assertEqual(parse_query_multimap("flag"), {"flag": [""]})

    def test_empty_query(self):
        self.assertEqual(parse_query_multimap(""), {})


if __name__ == "__main__":
    unittest.main()
