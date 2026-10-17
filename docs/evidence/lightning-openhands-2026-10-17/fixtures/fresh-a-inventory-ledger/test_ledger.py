import unittest

from ledger import InventoryLedger


class InventoryLedgerTests(unittest.TestCase):
    def test_reserve_and_release(self):
        ledger = InventoryLedger({"widget": 5})
        self.assertEqual(ledger.reserve("widget", 3), 2)
        self.assertEqual(ledger.release("widget", 1), 3)

    def test_failed_reservation_is_atomic(self):
        ledger = InventoryLedger({"widget": 2})
        with self.assertRaises(ValueError):
            ledger.reserve("widget", 3)
        self.assertEqual(ledger.available("widget"), 2)

    def test_cannot_release_more_than_reserved(self):
        ledger = InventoryLedger({"widget": 2})
        ledger.reserve("widget", 1)
        with self.assertRaises(ValueError):
            ledger.release("widget", 2)
        self.assertEqual(ledger.available("widget"), 1)

    def test_rejects_invalid_stock_and_quantities(self):
        with self.assertRaises(ValueError):
            InventoryLedger({"widget": -1})
        ledger = InventoryLedger({"widget": 2})
        for quantity in (0, -1, 1.5):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                ledger.reserve("widget", quantity)

    def test_unknown_sku(self):
        ledger = InventoryLedger({"widget": 2})
        with self.assertRaises(KeyError):
            ledger.reserve("missing", 1)


if __name__ == "__main__":
    unittest.main()
