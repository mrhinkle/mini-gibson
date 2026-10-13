# DEV TASK: dev-hard-d-discount
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: final_price(amount_cents, percent, fixed_cents) applies the percent to the original amount first, then subtracts the fixed cents, then floors at 0. Integer division truncates toward zero. percent is an integer from 0 through 100.

Examples:
- 200 cents, 25%, 0 fixed → 150
- 200 cents, 0%, 50 fixed → 150
- 1000 cents, 10%, 50 fixed → 850
- 100 cents, 0%, 500 fixed → 0

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
