import unittest
from inventory.store import Store
class T(unittest.TestCase):
    def test_bulk_at_threshold(self):
        s=Store(); s.add('a',10,1.0)
        self.assertEqual(s.total(),9.0)
    def test_remove_deletes_empty(self):
        s=Store(); s.add('a',2,1.0); s.remove('a',2)
        self.assertNotIn('a', s.items)
    def test_remove_missing_raises_keyerror_message(self):
        s=Store()
        with self.assertRaises(KeyError):
            s.remove('zzz',1)
if __name__=='__main__': unittest.main()
