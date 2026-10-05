import unittest
from cal import is_leap
class T(unittest.TestCase):
    def test_2024(self): self.assertTrue(is_leap(2024))
    def test_1900(self): self.assertFalse(is_leap(1900))
    def test_2000(self): self.assertTrue(is_leap(2000))
if __name__=='__main__': unittest.main()
