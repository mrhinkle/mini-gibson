import unittest
from counter import Counter
class T(unittest.TestCase):
    def test_reset(self):
        c=Counter(); c.inc(); c.inc(); c.reset()
        self.assertEqual(c.n,0)
if __name__=='__main__': unittest.main()
