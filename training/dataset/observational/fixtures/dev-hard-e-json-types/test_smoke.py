import json
import unittest
from jsondump.dump import dump_obj

class T(unittest.TestCase):
    def test_string(self):
        got = json.loads(dump_obj({"name": "a"}))
        self.assertEqual(got, {"name": "a"})
