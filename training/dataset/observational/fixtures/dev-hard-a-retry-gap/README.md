# DEV TASK: dev-hard-a-retry-gap
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #440).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: A job that is allowed N attempts is supposed to wait between attempts. The gap before attempt 2 is 10ms, then 20ms, then 40ms (doubling). One attempt has no gap. The schedule is a list of those gaps, not a live sleep.

Examples:
- 1 attempt → []
- 2 attempts → [10]
- 4 attempts → [10, 20, 40]

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
