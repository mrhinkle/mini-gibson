import unittest

from versions import sort_versions


class VersionTests(unittest.TestCase):
    def test_components_are_compared_numerically(self):
        values = ["1.10.0", "1.2.3", "2.0.0", "1.2.3", "0.12.9"]
        self.assertEqual(
            sort_versions(values),
            ["0.12.9", "1.2.3", "1.2.3", "1.10.0", "2.0.0"],
        )
        self.assertEqual(values, ["1.10.0", "1.2.3", "2.0.0", "1.2.3", "0.12.9"])

    def test_malformed_versions_are_rejected(self):
        for value in ["1.2", "1.2.3.4", "1.two.3", "1.-2.3", " 1.2.3"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                sort_versions([value])


if __name__ == "__main__":
    unittest.main()
