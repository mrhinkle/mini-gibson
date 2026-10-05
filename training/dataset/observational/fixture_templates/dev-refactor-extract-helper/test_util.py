import unittest
from util import process, process_names
class T(unittest.TestCase):
    def test_p(self): self.assertEqual(process([' A ','']), ['a'])
    def test_n(self): self.assertEqual(process_names([' Bob ']), ['bob'])
    def test_helper_exists(self):
        import util
        self.assertTrue(hasattr(util,'normalize') and callable(util.normalize))
        self.assertEqual(util.normalize(' X '), 'x')
if __name__=='__main__': unittest.main()
