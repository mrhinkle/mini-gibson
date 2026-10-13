# DEV TASK: dev-hard-c-cache-tombstone
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: Box is a single-process cache.
- get on a missing key returns None
- set then get returns the value
- invalidate(key) then get(key) returns None
- invalidate(key), then set(key, new), then get(key) returns new
- set A and B, invalidate A, get B still returns B

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
