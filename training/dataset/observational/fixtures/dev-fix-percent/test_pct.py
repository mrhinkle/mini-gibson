import unittest
from pct import percent
class T(unittest.TestCase):
    def test_p(self): self.assertEqual(percent(1,4),25.0)
if __name__=='__main__': unittest.main()
