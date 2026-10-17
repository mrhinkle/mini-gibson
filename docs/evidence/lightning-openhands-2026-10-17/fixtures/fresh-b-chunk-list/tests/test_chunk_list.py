import unittest

from chunk_list import chunk_list


class ChunkListTests(unittest.TestCase):
    def test_retains_final_partial_chunk(self):
        self.assertEqual(chunk_list([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_size_larger_than_input_still_returns_one_chunk(self):
        self.assertEqual(chunk_list([1, 2], 5), [[1, 2]])

    def test_empty_and_invalid_size(self):
        self.assertEqual(chunk_list([], 3), [])
        with self.assertRaises(ValueError):
            chunk_list([1], 0)


if __name__ == "__main__":
    unittest.main()
