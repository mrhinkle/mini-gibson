import unittest
from paths import join_path
class T(unittest.TestCase):
    def test_join(self): self.assertEqual(join_path('a','b','c'),'a/b/c')
    def test_abs(self): self.assertEqual(join_path('/a','b'),'/a/b')
if __name__=='__main__': unittest.main()
