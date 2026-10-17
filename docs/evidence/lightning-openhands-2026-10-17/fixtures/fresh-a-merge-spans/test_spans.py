import unittest

from spans import merge_spans


class MergeSpansTests(unittest.TestCase):
    def test_sorts_and_merges_overlap_and_touching(self):
        spans = [(8, 10), (1, 3), (3, 6), (9, 12)]
        self.assertEqual(merge_spans(spans), [(1, 6), (8, 12)])
        self.assertEqual(spans, [(8, 10), (1, 3), (3, 6), (9, 12)])

    def test_empty_and_disjoint(self):
        self.assertEqual(merge_spans([]), [])
        self.assertEqual(merge_spans([(1, 2), (4, 5)]), [(1, 2), (4, 5)])

    def test_invalid_span(self):
        with self.assertRaises(ValueError):
            merge_spans([(4, 3)])


if __name__ == "__main__":
    unittest.main()
