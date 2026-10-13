import unittest
from gates.feature import feature_enabled

class T(unittest.TestCase):
    def test_on(self):
        self.assertTrue(feature_enabled(True, None, "ada", set()))

    def test_env_off(self):
        self.assertFalse(feature_enabled(True, "0", "ada", set()))

    def test_denied(self):
        self.assertFalse(feature_enabled(True, None, "ada", {"ada"}))

    def test_file_off(self):
        self.assertFalse(feature_enabled(False, "1", "ada", set()))

    def test_env_on_other_denied(self):
        self.assertTrue(feature_enabled(True, "1", "ada", {"bob"}))
