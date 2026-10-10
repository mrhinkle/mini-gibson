import unittest
from roman import to_roman
class T(unittest.TestCase):
    def test_basic(self): self.assertEqual(to_roman(3),'III')
    def test_4(self): self.assertEqual(to_roman(4),'IV')
    def test_9(self): self.assertEqual(to_roman(9),'IX')
    def test_1994(self): self.assertEqual(to_roman(1994),'MCMXCIV')
if __name__=='__main__': unittest.main()
