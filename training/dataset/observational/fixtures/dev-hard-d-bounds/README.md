# DEV TASK: dev-hard-d-bounds
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: in_range(x, lo, hi) is inclusive on both ends when lo <= hi.
- in_range(1, 1, 3) is True
- in_range(3, 1, 3) is True
- in_range(2, 1, 3) is True
- in_range(0, 1, 3) is False
- in_range(4, 1, 3) is False
- When lo > hi the range is empty, so every x is False. Do not swap the ends.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
