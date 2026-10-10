import unittest
from sorty import sort_by_age
class T(unittest.TestCase):
    def test_s(self):
        people=[{'name':'a','age':30},{'name':'b','age':20}]
        self.assertEqual([p['name'] for p in sort_by_age(people)],['b','a'])
if __name__=='__main__': unittest.main()
