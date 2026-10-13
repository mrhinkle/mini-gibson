import unittest
from profiles.read import display
from profiles.write import write_record

class T(unittest.TestCase):
    def test_legacy(self):
        self.assertEqual(display({"name": "Ada"}), "Ada")

    def test_prefer_display(self):
        self.assertEqual(display({"display_name": "Grace", "name": "Old"}), "Grace")

    def test_write_keeps_legacy(self):
        rec = write_record("Ada")
        self.assertEqual(rec["name"], "Ada")
        self.assertEqual(rec["display_name"], "Ada")
        self.assertEqual(display(rec), "Ada")
