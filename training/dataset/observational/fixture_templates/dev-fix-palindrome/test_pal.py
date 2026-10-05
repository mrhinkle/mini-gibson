import unittest
from pal import is_palindrome
class T(unittest.TestCase):
    def test_simple(self): self.assertTrue(is_palindrome('racecar'))
    def test_case(self): self.assertTrue(is_palindrome('RaceCar'))
    def test_phrase(self): self.assertTrue(is_palindrome('A man a plan a canal Panama'))
    def test_no(self): self.assertFalse(is_palindrome('hello'))
if __name__=='__main__': unittest.main()
