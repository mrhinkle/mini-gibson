import unittest
from ostate.machine import can_transition

class T(unittest.TestCase):
    def test_legal(self):
        self.assertTrue(can_transition("draft", "submitted"))
        self.assertTrue(can_transition("submitted", "paid"))
        self.assertTrue(can_transition("submitted", "draft"))
        self.assertTrue(can_transition("paid", "shipped"))

    def test_skip_ship(self):
        self.assertFalse(can_transition("draft", "shipped"))

    def test_shipped_back(self):
        self.assertFalse(can_transition("shipped", "paid"))

    def test_paid_draft(self):
        self.assertFalse(can_transition("paid", "draft"))

    def test_same(self):
        self.assertFalse(can_transition("draft", "draft"))
