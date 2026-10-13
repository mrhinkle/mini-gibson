import unittest
from webfront.public import canonicalize_path

class T(unittest.TestCase):
    def test_space(self):
        self.assertEqual(canonicalize_path("/Hello World"), "/hello-world")

    def test_encoded_space(self):
        self.assertEqual(canonicalize_path("/Hello%20World"), "/hello-world")

    def test_underscores_and_slash(self):
        self.assertEqual(canonicalize_path("A__B/"), "/a-b")

    def test_already(self):
        self.assertEqual(canonicalize_path("/already"), "/already")
