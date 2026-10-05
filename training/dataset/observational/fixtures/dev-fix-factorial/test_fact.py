import unittest
from fact import factorial
class T(unittest.TestCase):
    def test_0(self): self.assertEqual(factorial(0), 1)
    def test_1(self): self.assertEqual(factorial(1), 1)
    def test_5(self): self.assertEqual(factorial(5), 120)
if __name__=='__main__': unittest.main()
