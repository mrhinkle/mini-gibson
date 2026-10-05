import unittest
from user import get
class T(unittest.TestCase):
    def test_get(self): self.assertEqual(get(),42)
    def test_new_module(self):
        import importlib.util
        spec=importlib.util.find_spec('newname')
        self.assertIsNotNone(spec)
if __name__=='__main__': unittest.main()
