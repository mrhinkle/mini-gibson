import unittest
from csvutil import headers
class T(unittest.TestCase):
    def test_h(self): self.assertEqual(headers('a, b, c'),['a','b','c'])
if __name__=='__main__': unittest.main()
