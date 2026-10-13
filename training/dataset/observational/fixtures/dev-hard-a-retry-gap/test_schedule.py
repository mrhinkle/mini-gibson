import unittest
from jobs.api import schedule

class T(unittest.TestCase):
    def test_once(self):
        self.assertEqual(schedule(1), [])

    def test_twice(self):
        self.assertEqual(schedule(2), [10])

    def test_four(self):
        self.assertEqual(schedule(4), [10, 20, 40])
