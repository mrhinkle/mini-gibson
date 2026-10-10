import unittest
from lru import LRU
class T(unittest.TestCase):
    def test_recency(self):
        c=LRU(2); c.put('a',1); c.put('b',2)
        c.get('a')
        c.put('c',3)
        self.assertEqual(c.get('a'),1)
        self.assertIsNone(c.get('b'))
    def test_update_refreshes(self):
        c=LRU(2); c.put('a',1); c.put('b',2); c.put('a',10); c.put('c',3)
        self.assertEqual(c.get('a'),10)
        self.assertIsNone(c.get('b'))
if __name__=='__main__': unittest.main()
