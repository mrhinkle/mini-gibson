import unittest
from parse import parse_ints
class T(unittest.TestCase):
    def test_basic(self): self.assertEqual(parse_ints('1,2,3'),[1,2,3])
    def test_spaces(self): self.assertEqual(parse_ints('1, 2, 3'),[1,2,3])
    def test_trailing(self): self.assertEqual(parse_ints('1,2,'),[1,2])
if __name__=='__main__': unittest.main()
