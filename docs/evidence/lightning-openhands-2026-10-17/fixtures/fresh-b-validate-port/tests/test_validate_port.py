import unittest

from validate_port import validate_port


class ValidatePortTests(unittest.TestCase):
    def test_valid_boundaries(self):
        self.assertEqual(validate_port(1), 1)
        self.assertEqual(validate_port(65535), 65535)

    def test_boolean_is_not_an_integer_port(self):
        with self.assertRaises(TypeError):
            validate_port(True)
        with self.assertRaises(TypeError):
            validate_port(False)

    def test_other_types_and_ranges(self):
        with self.assertRaises(TypeError):
            validate_port("443")
        for value in (0, 65536):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_port(value)


if __name__ == "__main__":
    unittest.main()
