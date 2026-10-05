import unittest
from stats import average
class T(unittest.TestCase):
    def test_basic(self): self.assertAlmostEqual(average([1,2,3]), 2.0)
    def test_one(self): self.assertAlmostEqual(average([7]), 7.0)
if __name__=='__main__': unittest.main()
