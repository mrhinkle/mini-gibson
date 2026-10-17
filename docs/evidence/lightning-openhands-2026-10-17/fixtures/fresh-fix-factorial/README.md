# Repair factorial edge cases

`math_helpers.factorial(n)` should return the factorial for every non-negative
integer, including `0`, and raise `ValueError` for negative inputs. The current
implementation mishandles edge cases.

Make the smallest correct change and run `python3 -m unittest -q`.
