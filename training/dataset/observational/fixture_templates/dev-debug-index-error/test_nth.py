import unittest
from nth import nth
class T(unittest.TestCase):
    def test_ok(self): self.assertEqual(nth([10,20],1),20)
    def test_oob(self): self.assertIsNone(nth([10],5))
if __name__=='__main__': unittest.main()
