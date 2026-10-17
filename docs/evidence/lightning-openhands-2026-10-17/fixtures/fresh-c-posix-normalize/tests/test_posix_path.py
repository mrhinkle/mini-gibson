import unittest

from posix_path import normalize_posix


class PosixNormalizeTests(unittest.TestCase):
    def test_relative_normalization(self):
        self.assertEqual(normalize_posix("a//./b/../c"), "a/c")
        self.assertEqual(normalize_posix("a/../../b"), "../b")
        self.assertEqual(normalize_posix(""), ".")

    def test_absolute_normalization_and_root_floor(self):
        self.assertEqual(normalize_posix("/a/../../b"), "/b")
        self.assertEqual(normalize_posix("//srv///app"), "/srv/app")
        self.assertEqual(normalize_posix("////"), "/")

    def test_invalid_input(self):
        for value in [None, 4, "a\x00b"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_posix(value)


if __name__ == "__main__":
    unittest.main()
