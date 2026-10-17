# Inventory reservation ledger

`InventoryLedger(stock)` tracks available non-negative integer quantities. `reserve(sku, quantity)` subtracts only when enough stock exists. `release(sku, quantity)` restores only previously reserved stock. Unknown SKUs raise `KeyError`; invalid quantities and invariant violations raise `ValueError`. Failed operations must not mutate state.

Only `ledger.py` may be changed.
