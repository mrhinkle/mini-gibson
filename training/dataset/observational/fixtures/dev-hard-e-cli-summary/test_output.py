import io
import unittest
from contextlib import redirect_stdout
from summary.cli import summarize

class T(unittest.TestCase):
    def test_line(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = summarize([2, 3])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), "count=2 total=5\n")

    def test_empty(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            summarize([])
        self.assertEqual(buf.getvalue(), "count=0 total=0\n")
