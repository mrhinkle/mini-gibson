import unittest
from greeting import greet

class TestGreet(unittest.TestCase):
    def test_greet_alice(self):
        self.assertEqual(greet("Alice"), "Hello, Alice!")

    def test_greet_empty_uses_world(self):
        self.assertEqual(greet(""), "Hello, World!")

if __name__ == "__main__":
    unittest.main()
