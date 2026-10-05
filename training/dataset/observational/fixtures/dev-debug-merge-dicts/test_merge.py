import unittest
from merge import merge
class T(unittest.TestCase):
    def test_no_mutate(self):
        a={'x':1}; b={'y':2}
        r=merge(a,b)
        self.assertEqual(r,{'x':1,'y':2})
        self.assertEqual(a,{'x':1})  # must not mutate
    def test_overlap(self):
        self.assertEqual(merge({'a':1},{'a':2}),{'a':2})
if __name__=='__main__': unittest.main()
