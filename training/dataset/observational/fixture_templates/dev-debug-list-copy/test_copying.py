import unittest
from copying import with_item
class T(unittest.TestCase):
    def test_no_mutate(self):
        xs=[1,2]
        r=with_item(xs,3)
        self.assertEqual(r,[1,2,3])
        self.assertEqual(xs,[1,2])
if __name__=='__main__': unittest.main()
