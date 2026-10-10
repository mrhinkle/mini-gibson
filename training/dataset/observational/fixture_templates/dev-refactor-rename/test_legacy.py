import unittest
import legacy
class T(unittest.TestCase):
    def test_new_name(self):
        self.assertTrue(hasattr(legacy,'calculate_tax'))
        self.assertEqual(legacy.calculate_tax(100),7.0)
    def test_old_gone_or_alias(self):
        # old name may remain as alias but calculate_tax must exist
        self.assertEqual(legacy.calculate_tax(100),7.0)
if __name__=='__main__': unittest.main()
