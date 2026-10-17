import unittest

from word_wrap import wrap_words


class WordWrapTests(unittest.TestCase):
    def test_greedy_wrapping(self):
        self.assertEqual(wrap_words("one two three four", 7), ["one two", "three", "four"])

    def test_arbitrary_whitespace_is_normalized(self):
        self.assertEqual(wrap_words("  alpha\n beta\t gamma  ", 10), ["alpha beta", "gamma"])

    def test_long_word_is_retained_alone(self):
        self.assertEqual(wrap_words("a extraordinary word", 5), ["a", "extraordinary", "word"])

    def test_empty_text(self):
        self.assertEqual(wrap_words(" \n\t ", 4), [])

    def test_invalid_input(self):
        for args in [(None, 4), ("text", 0), ("text", True), ("text", 2.5)]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    wrap_words(*args)


if __name__ == "__main__":
    unittest.main()
