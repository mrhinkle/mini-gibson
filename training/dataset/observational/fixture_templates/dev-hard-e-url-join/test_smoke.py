import unittest
from urljoin.join import join_url

class T(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(join_url("https://ex.com", "a"), "https://ex.com/a")
