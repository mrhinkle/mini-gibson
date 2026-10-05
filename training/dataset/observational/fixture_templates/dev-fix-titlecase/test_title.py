import unittest
from title import titlecase
class T(unittest.TestCase):
    def test_t(self): self.assertEqual(titlecase('hello world'),'Hello World')
if __name__=='__main__': unittest.main()
