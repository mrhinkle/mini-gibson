import unittest
from sumto import sum_to_n

class TestSumTo(unittest.TestCase):
    def test_sum_to_5(self):
        self.assertEqual(sum_to_n(5), 15)

    def test_sum_to_1(self):
        self.assertEqual(sum_to_n(1), 1)

    def test_sum_to_0(self):
        self.assertEqual(sum_to_n(0), 0)

if __name__ == "__main__":
    unittest.main()
