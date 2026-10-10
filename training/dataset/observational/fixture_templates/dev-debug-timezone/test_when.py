import unittest
from when import epoch_to_iso
class T(unittest.TestCase):
    def test_epoch0(self):
        s=epoch_to_iso(0)
        self.assertTrue(s.startswith('1970-01-01T00:00:00'))
        self.assertTrue(s.endswith('+00:00') or s.endswith('Z'))
if __name__=='__main__': unittest.main()
