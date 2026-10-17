import unittest

from text_utils import slugify


class SlugifyTests(unittest.TestCase):
    def test_words_and_case(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_collapses_and_strips(self):
        self.assertEqual(slugify("  One---Two___Three! "), "one-two-three")

    def test_empty_after_cleanup(self):
        self.assertEqual(slugify("***"), "")


if __name__ == "__main__":
    unittest.main()
