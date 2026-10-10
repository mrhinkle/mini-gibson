import unittest
from mask import mask_email
class T(unittest.TestCase):
    def test_mask(self):
        self.assertEqual(mask_email('ada@example.com'),'a***@example.com')
if __name__=='__main__': unittest.main()
