import unittest
from listen.resolve import resolve_port

class T(unittest.TestCase):
    def test_default(self):
        self.assertEqual(resolve_port(None, {}, None), 8080)

    def test_file(self):
        self.assertEqual(resolve_port(None, {}, 9000), 9000)

    def test_env_beats_file(self):
        self.assertEqual(resolve_port(None, {"PORT": "7000"}, 9000), 7000)

    def test_empty_env_keeps_file(self):
        self.assertEqual(resolve_port(None, {"PORT": ""}, 9000), 9000)

    def test_empty_env_default(self):
        self.assertEqual(resolve_port(None, {"PORT": ""}, None), 8080)

    def test_cli_beats_all(self):
        self.assertEqual(resolve_port(3000, {"PORT": "7000"}, 9000), 3000)
