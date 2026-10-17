import unittest

from flatten import flatten_mapping


class FlattenMappingTests(unittest.TestCase):
    def test_recursive_flatten(self):
        value = {"app": {"db": {"host": "localhost", "port": 5432}}, "debug": False}
        self.assertEqual(
            flatten_mapping(value),
            {"app.db.host": "localhost", "app.db.port": 5432, "debug": False},
        )

    def test_custom_separator_and_empty_mapping(self):
        self.assertEqual(flatten_mapping({"a": {"b": 1}}, "/"), {"a/b": 1})
        self.assertEqual(flatten_mapping({"a": {}, "b": 2}), {"b": 2})

    def test_collision_is_rejected(self):
        with self.assertRaises(ValueError):
            flatten_mapping({"a.b": 1, "a": {"b": 2}})

    def test_invalid_keys_and_separator(self):
        for value in [{"": 1}, {1: "one"}]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    flatten_mapping(value)
        with self.assertRaises(ValueError):
            flatten_mapping({"a": 1}, "")

    def test_input_is_not_mutated(self):
        value = {"a": {"b": 1}}
        flatten_mapping(value)
        self.assertEqual(value, {"a": {"b": 1}})


if __name__ == "__main__":
    unittest.main()
