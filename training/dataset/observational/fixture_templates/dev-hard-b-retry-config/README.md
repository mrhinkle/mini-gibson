# DEV TASK: dev-hard-b-retry-config
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: retry_count is the number of extra attempts after the first. The worker's attempt total is retry_count + 1.
- When the config mapping is missing or has no retry_count key, retry_count is 3 (4 attempts).
- retry_count 0 is real and means exactly 1 attempt. It is not "missing".
- retry_count 2 means 3 attempts.

load(data) returns {"retry_count": n}. attempts(cfg) returns the attempt total.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
