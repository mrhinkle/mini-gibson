import unittest
import tcache.api as api

class T(unittest.TestCase):
    def setUp(self):
        api.reset()

    def test_isolated(self):
        api.set_value("a", "color", "red")
        api.set_value("b", "color", "blue")
        self.assertEqual(api.get_value("a", "color"), "red")
        self.assertEqual(api.get_value("b", "color"), "blue")

    def test_missing(self):
        self.assertIsNone(api.get_value("a", "missing"))
