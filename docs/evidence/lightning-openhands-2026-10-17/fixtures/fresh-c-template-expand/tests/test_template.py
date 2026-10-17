import unittest

from template import expand_template


class TemplateExpandTests(unittest.TestCase):
    def test_replaces_repeated_placeholders(self):
        self.assertEqual(
            expand_template("${name}: ${count} for ${name}", {"name": "Ada", "count": 2}),
            "Ada: 2 for Ada",
        )

    def test_dollar_escape(self):
        self.assertEqual(expand_template("cost $$${amount}", {"amount": 5}), "cost $5")

    def test_missing_name(self):
        with self.assertRaises(KeyError):
            expand_template("hello ${name}", {})

    def test_malformed_template(self):
        for template in ["$name", "${}", "${1name}", "${name", "trailing $"]:
            with self.subTest(template=template):
                with self.assertRaises(ValueError):
                    expand_template(template, {"name": "Ada"})

    def test_invalid_top_level_inputs(self):
        for template, values in [(None, {}), ("ok", None), ("ok", [])]:
            with self.subTest(template=template, values=values):
                with self.assertRaises(ValueError):
                    expand_template(template, values)


if __name__ == "__main__":
    unittest.main()
