import unittest
from lines import trim_lines
class T(unittest.TestCase):
    def test_t(self):
        self.assertEqual(trim_lines(' a \n\n b \n'),['a','b'])
if __name__=='__main__': unittest.main()
