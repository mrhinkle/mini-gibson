import unittest
from gcd import gcd
class T(unittest.TestCase):
    def test_g(self): self.assertEqual(gcd(54,24),6)
    def test_p(self): self.assertEqual(gcd(17,13),1)
if __name__=='__main__': unittest.main()
