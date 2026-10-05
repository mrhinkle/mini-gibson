import unittest
from slug import slugify
class T(unittest.TestCase):
    def test_basic(self): self.assertEqual(slugify('Hello World'), 'hello-world')
    def test_multi(self): self.assertEqual(slugify('Foo   Bar'), 'foo-bar')
if __name__=='__main__': unittest.main()
