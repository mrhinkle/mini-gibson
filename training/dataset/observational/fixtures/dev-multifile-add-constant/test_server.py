import unittest
import constants, server
class T(unittest.TestCase):
    def test_port_constant(self):
        self.assertEqual(constants.PORT,8080)
    def test_banner(self):
        self.assertIn('8080', server.banner())
if __name__=='__main__': unittest.main()
