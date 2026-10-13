# DEV TASK: dev-hard-c-idempotent-credit
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: apply_credit(balance, amount, key, seen) posts a credit once per key.
- key is required; "" or None raises ValueError("missing key")
- the first time a key is seen, add amount to balance and record the key in seen
- the same key again returns the balance unchanged
- a different key posts again

seen is a set the caller owns. Do not treat two different keys as the same just because the amount matches.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
