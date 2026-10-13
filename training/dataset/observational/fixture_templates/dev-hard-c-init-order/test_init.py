import unittest
from bootcfg.init import build_config

class T(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(build_config(None), {"theme": "light", "plugins": ["core"]})
        self.assertEqual(build_config({}), {"theme": "light", "plugins": ["core"]})

    def test_theme(self):
        got = build_config({"theme": "dark"})
        self.assertEqual(got["theme"], "dark")
        self.assertEqual(got["plugins"], ["core"])

    def test_plugins_replace(self):
        self.assertEqual(build_config({"plugins": ["extra"]})["plugins"], ["extra"])

    def test_extra_key(self):
        got = build_config({"theme": "dark", "banner": True})
        self.assertEqual(got["theme"], "dark")
        self.assertEqual(got["banner"], True)
