class InventoryLedger:
    def __init__(self, stock):
        self._available = dict(stock)

    def available(self, sku):
        return self._available[sku]

    def reserve(self, sku, quantity):
        self._available[sku] -= quantity
        if self._available[sku] < 0:
            raise ValueError("insufficient stock")
        return self._available[sku]

    def release(self, sku, quantity):
        self._available[sku] += quantity
        return self._available[sku]
