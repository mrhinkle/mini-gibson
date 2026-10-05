import unittest
from rot import rotate_left
class T(unittest.TestCase):
    def test_r(self): self.assertEqual(rotate_left([1,2,3,4],1),[2,3,4,1])
    def test_k2(self): self.assertEqual(rotate_left([1,2,3,4],2),[3,4,1,2])
if __name__=='__main__': unittest.main()
