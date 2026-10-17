import unittest

from balanced_brackets import brackets_balanced


class BalancedBracketTests(unittest.TestCase):
    def test_properly_nested_and_non_brackets(self):
        self.assertTrue(brackets_balanced("call({items: [1, 2]})"))
        self.assertTrue(brackets_balanced("plain text"))

    def test_mismatched_nesting_is_false(self):
        self.assertFalse(brackets_balanced("([)]"))
        self.assertFalse(brackets_balanced("]foo["))

    def test_unclosed_bracket_is_false(self):
        self.assertFalse(brackets_balanced("{value"))


if __name__ == "__main__":
    unittest.main()
