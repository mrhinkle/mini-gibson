import unittest
from phones.fmt import format_phone

class T(unittest.TestCase):
    def test_ten_punct(self):
        self.assertEqual(format_phone("(555) 123-4567"), "+15551234567")

    def test_ten_plain(self):
        self.assertEqual(format_phone("5551234567"), "+15551234567")

    def test_eleven(self):
        self.assertEqual(format_phone("15551234567"), "+15551234567")

    def test_uk(self):
        self.assertEqual(format_phone("+44 20 7946 0958"), "+442079460958")

    def test_short(self):
        with self.assertRaises(ValueError):
            format_phone("123")
