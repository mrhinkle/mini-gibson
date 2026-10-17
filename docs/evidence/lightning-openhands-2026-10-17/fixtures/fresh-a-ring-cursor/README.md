# Circular cursor

`RingCursor(items)` tracks a current item in a non-empty sequence. `advance(steps=1)` must wrap for positive and negative integer steps and return the new current item. Construction with no items must raise `ValueError`.

Only `ring.py` may be changed.
