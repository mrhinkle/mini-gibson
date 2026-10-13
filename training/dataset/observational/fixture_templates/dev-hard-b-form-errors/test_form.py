import unittest
from signup.http import handle

class T(unittest.TestCase):
    def test_missing_name(self):
        status, body = handle({"name": "  ", "email": "a@b.co"})
        self.assertEqual(status, 400)
        self.assertIn("required", body["errors"])

    def test_bad_email(self):
        status, body = handle({"name": "Ada", "email": "nope"})
        self.assertEqual(status, 400)
        self.assertIn("format", body["errors"])

    def test_ok(self):
        status, body = handle({"name": "Ada", "email": "a@b.co"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
