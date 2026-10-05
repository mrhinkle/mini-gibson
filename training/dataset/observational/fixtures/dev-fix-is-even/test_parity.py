import unittest
from parity import is_even
class T(unittest.TestCase):
    def test_e(self): self.assertTrue(is_even(4))
    def test_o(self): self.assertFalse(is_even(3))
if __name__=='__main__': unittest.main()
