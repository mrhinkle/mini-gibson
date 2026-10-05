import unittest
from case import to_kebab
class T(unittest.TestCase):
    def test_k(self): self.assertEqual(to_kebab('HelloWorld'),'hello-world')
    def test_u(self): self.assertEqual(to_kebab('hello_world'),'hello-world')
if __name__=='__main__': unittest.main()
