import unittest
from authz.api import permitted

class T(unittest.TestCase):
    def test_admin_billing(self):
        self.assertTrue(permitted("admin", "billing"))

    def test_admin_read(self):
        self.assertTrue(permitted("admin", "read"))

    def test_member_read(self):
        self.assertTrue(permitted("member", "read"))

    def test_member_billing(self):
        self.assertFalse(permitted("member", "billing"))

    def test_guest(self):
        self.assertFalse(permitted("guest", "read"))
