import unittest

from redact import redact_token


class RedactTokenTests(unittest.TestCase):
    def test_long_token_keeps_suffix(self):
        self.assertEqual(redact_token("abcdefgh", 3), "*****fgh")

    def test_short_token_is_fully_redacted(self):
        self.assertEqual(redact_token("abc", 4), "***")

    def test_zero_visible_redacts_everything(self):
        self.assertEqual(redact_token("secret", 0), "******")

    def test_rejects_invalid_inputs(self):
        for token, visible in ((None, 4), ("abc", -1), ("abc", 1.5)):
            with self.subTest(token=token, visible=visible), self.assertRaises(ValueError):
                redact_token(token, visible)


if __name__ == "__main__":
    unittest.main()
