import unittest
from runner.config import load
from runner.worker import attempts

class T(unittest.TestCase):
    def test_default(self):
        self.assertEqual(attempts(load(None)), 4)
        self.assertEqual(attempts(load({})), 4)

    def test_zero(self):
        cfg = load({"retry_count": 0})
        self.assertEqual(cfg["retry_count"], 0)
        self.assertEqual(attempts(cfg), 1)

    def test_two(self):
        self.assertEqual(attempts(load({"retry_count": 2})), 3)
