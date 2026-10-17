import unittest

from rotate_list import rotate_right


class RotateListTests(unittest.TestCase):
    def test_steps_larger_than_length_wrap(self):
        self.assertEqual(rotate_right([1, 2, 3, 4], 6), [3, 4, 1, 2])

    def test_negative_steps_rotate_left(self):
        self.assertEqual(rotate_right([1, 2, 3, 4], -1), [2, 3, 4, 1])

    def test_empty_and_no_mutation(self):
        values = [1, 2, 3]
        self.assertEqual(rotate_right([], 99), [])
        self.assertEqual(rotate_right(values, 3), [1, 2, 3])
        self.assertEqual(values, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
