# DEV TASK: dev-hard-c-timeout-absent
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: timeout_seconds(data) reads the "timeout" field.
- Key absent → 30
- Value "" → raise ValueError
- Value "0" → 0 (a real disable, not the default)
- Value "15" → 15

Absent and empty are different. Zero and absent are different.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
