import unittest

from greeter import greeting


class GreetingTests(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(greeting(" Ada "), "Hello, Ada.")

    def test_excited(self):
        self.assertEqual(greeting("Grace", excited=True), "Hello, Grace!")

    def test_empty_name(self):
        with self.assertRaises(ValueError):
            greeting("   ")


if __name__ == "__main__":
    unittest.main()
