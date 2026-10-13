# DEV TASK: dev-hard-b-invoice-total
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: An invoice has two rules, and both are wrong in production.
- A line's subtotal is quantity times unit price in cents. When quantity is greater than or equal to 10, apply a 10% discount (1000 basis points) to that line, using integer math that truncates toward zero.
- Tax is the order's own tax_bps (basis points). 0 means no tax. 1000 means 10%. Tax truncates toward zero. Do not assume a fixed 5% rate.

Examples (unit price 100 cents):
- qty 10, tax_bps 0 → subtotal 900, tax 0, total 900
- qty 9, tax_bps 0 → subtotal 900, tax 0, total 900
- qty 1, tax_bps 1000 → subtotal 100, tax 10, total 110
- qty 1, tax_bps 0 → subtotal 100, tax 0, total 100

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
