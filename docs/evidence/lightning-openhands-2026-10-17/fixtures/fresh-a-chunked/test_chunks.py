import unittest

from chunks import chunked


class ChunkedTests(unittest.TestCase):
    def test_keeps_partial_tail_from_generator(self):
        source = (number for number in range(5))
        self.assertEqual(list(chunked(source, 2)), [[0, 1], [2, 3], [4]])

    def test_empty_and_large_size(self):
        self.assertEqual(list(chunked([], 3)), [])
        self.assertEqual(list(chunked([1, 2], 10)), [[1, 2]])

    def test_rejects_invalid_sizes(self):
        for size in (0, -1, 1.5):
            with self.subTest(size=size), self.assertRaises(ValueError):
                list(chunked([1], size))


if __name__ == "__main__":
    unittest.main()
