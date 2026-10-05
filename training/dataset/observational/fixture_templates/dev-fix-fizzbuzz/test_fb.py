import unittest
from fb import fizzbuzz
class T(unittest.TestCase):
    def test15(self):
        r=fizzbuzz(15)
        self.assertEqual(r[2],'Fizz')
        self.assertEqual(r[4],'Buzz')
        self.assertEqual(r[14],'FizzBuzz')
if __name__=='__main__': unittest.main()
