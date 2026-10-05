import unittest
from stack import Stack
class T(unittest.TestCase):
    def test_pop(self):
        s=Stack(); s.push(1); s.push(2)
        self.assertEqual(s.pop(),2)
        self.assertEqual(s.size(),1)
if __name__=='__main__': unittest.main()
