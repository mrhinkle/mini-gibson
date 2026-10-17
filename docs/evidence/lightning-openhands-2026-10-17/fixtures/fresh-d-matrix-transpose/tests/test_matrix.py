import unittest

from matrix import transpose


class MatrixTests(unittest.TestCase):
    def test_rectangular_and_empty_matrices(self):
        matrix = [[1, 2, 3], [4, 5, 6]]
        self.assertEqual(transpose(matrix), [[1, 4], [2, 5], [3, 6]])
        self.assertEqual(matrix, [[1, 2, 3], [4, 5, 6]])
        self.assertEqual(transpose([]), [])
        self.assertEqual(transpose([[], []]), [])

    def test_ragged_matrix_is_rejected(self):
        with self.assertRaises(ValueError):
            transpose([[1, 2], [3]])


if __name__ == "__main__":
    unittest.main()
