import unittest
from uniq import unique_preserve
class T(unittest.TestCase):
    def test_order(self): self.assertEqual(unique_preserve([1,2,1,3,2]), [1,2,3])
    def test_empty(self): self.assertEqual(unique_preserve([]), [])
if __name__=='__main__': unittest.main()
