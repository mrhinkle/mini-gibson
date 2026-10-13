import unittest
from urljoin.join import join_url

class T(unittest.TestCase):
    def test_trailing_slash(self):
        self.assertEqual(join_url("https://ex.com/", "a"), "https://ex.com/a")

    def test_query(self):
        self.assertEqual(join_url("https://ex.com/a", "b?x=1"), "https://ex.com/a/b?x=1")

    def test_both_slashes(self):
        self.assertEqual(join_url("https://ex.com/a/", "/b"), "https://ex.com/a/b")

    def test_empty_path(self):
        self.assertEqual(join_url("https://ex.com/a", ""), "https://ex.com/a")
