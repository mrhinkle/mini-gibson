import unittest
from evlog.emit import emit
from evlog.read import read_event

class T(unittest.TestCase):
    def test_round_trip(self):
        payload = emit("ping", 1700000000123)
        self.assertEqual(payload["ts"], 1700000000123)
        self.assertEqual(read_event(payload)["ts_ms"], 1700000000123)

    def test_existing_millis(self):
        got = read_event({"kind": "x", "ts": 1700000000000})
        self.assertEqual(got["ts_ms"], 1700000000000)
