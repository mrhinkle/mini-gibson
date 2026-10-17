# Apportion integer cents

`apportion_cents(total, weights)` must split a non-negative integer total according to non-negative weights. Return integer shares whose sum exactly equals `total`. Use largest-remainder allocation, breaking equal fractional remainders by lower input index. Reject empty, all-zero, negative, or non-integer inputs with `ValueError`.

Only `allocation.py` may be changed.
