import unittest
from summary.cli import summarize

class T(unittest.TestCase):
    def test_exit(self):
        self.assertEqual(summarize([2, 3]), 0)
