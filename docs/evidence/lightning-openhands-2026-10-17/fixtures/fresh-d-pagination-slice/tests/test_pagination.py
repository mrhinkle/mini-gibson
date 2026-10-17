import unittest

from pagination import page_slice


class PaginationTests(unittest.TestCase):
    def test_pages_are_one_based_and_partial_page_is_kept(self):
        values = ["a", "b", "c", "d", "e"]
        self.assertEqual(page_slice(values, 1, 2), ["a", "b"])
        self.assertEqual(page_slice(values, 3, 2), ["e"])
        self.assertEqual(page_slice(values, 4, 2), [])
        self.assertEqual(values, ["a", "b", "c", "d", "e"])

    def test_boolean_and_non_positive_arguments_are_rejected(self):
        for page, size in [(True, 2), (1, False), (0, 2), (1, -1)]:
            with self.subTest(page=page, size=size), self.assertRaises(ValueError):
                page_slice([], page, size)


if __name__ == "__main__":
    unittest.main()
