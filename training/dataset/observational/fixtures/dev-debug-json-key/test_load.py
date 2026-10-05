import unittest
from load import db_port
class T(unittest.TestCase):
    def test_port(self): self.assertEqual(db_port(),5432)
if __name__=='__main__': unittest.main()
