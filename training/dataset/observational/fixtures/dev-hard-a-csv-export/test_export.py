import unittest
from exporting.api import export_rows

class T(unittest.TestCase):
    def test_zero_and_empty(self):
        text = export_rows([{"sku": "a", "qty": 0, "note": ""}], ["sku", "qty", "note"])
        self.assertEqual(text, "sku,qty,note\na,0,\n")

    def test_comma(self):
        text = export_rows([{"sku": "a", "qty": 1, "note": "red, blue"}], ["sku", "qty", "note"])
        self.assertEqual(text, 'sku,qty,note\na,1,"red, blue"\n')

    def test_quote(self):
        text = export_rows([{"sku": "a", "qty": 2, "note": 'say "hi"'}], ["sku", "qty", "note"])
        self.assertEqual(text, 'sku,qty,note\na,2,"say ""hi"""\n')
