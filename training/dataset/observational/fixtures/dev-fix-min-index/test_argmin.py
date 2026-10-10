import unittest
from argmin import min_index
class T(unittest.TestCase):
    def test_m(self): self.assertEqual(min_index([3,1,2]),1)
if __name__=='__main__': unittest.main()
