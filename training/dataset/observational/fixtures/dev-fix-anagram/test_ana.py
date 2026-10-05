import unittest
from ana import anagrams
class T(unittest.TestCase):
    def test_yes(self): self.assertTrue(anagrams('listen','silent'))
    def test_no(self): self.assertFalse(anagrams('hello','world'))
    def test_case(self): self.assertTrue(anagrams('Listen','Silent'))
if __name__=='__main__': unittest.main()
