import unittest

from ring import RingCursor


class RingCursorTests(unittest.TestCase):
    def test_wraps_forward_and_backward(self):
        cursor = RingCursor(["a", "b", "c"])
        self.assertEqual(cursor.advance(4), "b")
        self.assertEqual(cursor.advance(-2), "c")

    def test_single_item_is_stable(self):
        cursor = RingCursor(["only"])
        self.assertEqual(cursor.advance(99), "only")

    def test_empty_is_rejected(self):
        with self.assertRaises(ValueError):
            RingCursor([])


if __name__ == "__main__":
    unittest.main()
