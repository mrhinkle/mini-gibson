import unittest
from div import safe_div
class T(unittest.TestCase):
    def test_ok(self): self.assertEqual(safe_div(10,2),5)
    def test_zero(self): self.assertIsNone(safe_div(1,0))
if __name__=='__main__': unittest.main()
