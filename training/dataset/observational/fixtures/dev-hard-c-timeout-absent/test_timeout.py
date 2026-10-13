import unittest
from timing.load import timeout_seconds

class T(unittest.TestCase):
    def test_absent(self):
        self.assertEqual(timeout_seconds({}), 30)
        self.assertEqual(timeout_seconds(None), 30)

    def test_empty(self):
        with self.assertRaises(ValueError):
            timeout_seconds({"timeout": ""})

    def test_zero(self):
        self.assertEqual(timeout_seconds({"timeout": "0"}), 0)

    def test_fifteen(self):
        self.assertEqual(timeout_seconds({"timeout": "15"}), 15)
