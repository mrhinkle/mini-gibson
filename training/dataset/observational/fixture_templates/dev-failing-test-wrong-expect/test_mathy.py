import unittest
from mathy import double
class T(unittest.TestCase):
    def test_double(self):
        # The implementation is correct; this expectation is wrong.
        # Fix the TEST to match correct behavior (2*2==4), do not break double().
        self.assertEqual(double(2),5)
if __name__=='__main__': unittest.main()
