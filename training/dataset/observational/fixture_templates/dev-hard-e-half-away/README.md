# DEV TASK: dev-hard-e-half-away
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: round_half_away(x) rounds half away from zero, for positive and negative numbers.
- 1.2 → 1
- 1.5 → 2
- 2.5 → 3
- -1.5 → -2
- -2.5 → -3
Ties at .5 do not use banker's rounding.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
