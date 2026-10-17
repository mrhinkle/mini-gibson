import unittest

from byte_size import format_bytes


class FormatBytesTests(unittest.TestCase):
    def test_bytes_and_binary_thresholds(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1023), "1023 B")
        self.assertEqual(format_bytes(1024), "1.0 KiB")
        self.assertEqual(format_bytes(1536), "1.5 KiB")

    def test_larger_units_and_tib_cap(self):
        self.assertEqual(format_bytes(2**20), "1.0 MiB")
        self.assertEqual(format_bytes(3 * 2**30), "3.0 GiB")
        self.assertEqual(format_bytes(2**50), "1024.0 TiB")

    def test_invalid_input(self):
        for value in [-1, True, 1.5, "1024", None]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    format_bytes(value)


if __name__ == "__main__":
    unittest.main()
