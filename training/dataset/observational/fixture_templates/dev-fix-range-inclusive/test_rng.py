import unittest
from rng import inclusive_range
class T(unittest.TestCase):
    def test_r(self): self.assertEqual(inclusive_range(1,3),[1,2,3])
if __name__=='__main__': unittest.main()
