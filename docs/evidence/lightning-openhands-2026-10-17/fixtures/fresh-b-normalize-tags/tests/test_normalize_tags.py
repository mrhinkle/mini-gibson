import unittest

from normalize_tags import normalize_tags


class NormalizeTagsTests(unittest.TestCase):
    def test_collapses_whitespace_before_deduplication(self):
        self.assertEqual(
            normalize_tags(["  Machine\t Learning ", "machine learning", "AI", " ai "]),
            ["machine learning", "ai"],
        )

    def test_unicode_casefold_and_blank_omission(self):
        self.assertEqual(normalize_tags(["Straße", "STRASSE", " \n "]), ["strasse"])


if __name__ == "__main__":
    unittest.main()
