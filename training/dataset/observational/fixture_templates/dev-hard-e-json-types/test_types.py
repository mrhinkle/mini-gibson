import json
import unittest
from jsondump.dump import dump_obj

class T(unittest.TestCase):
    def test_types(self):
        got = json.loads(dump_obj({"n": 2, "ok": True, "note": None}))
        self.assertEqual(got["n"], 2)
        self.assertIs(got["ok"], True)
        self.assertIsNone(got["note"])
