import unittest
from chunk import chunked
class T(unittest.TestCase):
    def test_c(self): self.assertEqual(chunked([1,2,3,4,5],2),[[1,2],[3,4],[5]])
if __name__=='__main__': unittest.main()
