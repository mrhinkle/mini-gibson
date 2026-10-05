import unittest
from flat import flatten
class T(unittest.TestCase):
    def test_f(self): self.assertEqual(flatten([[1,2],[3],[]]),[1,2,3])
if __name__=='__main__': unittest.main()
