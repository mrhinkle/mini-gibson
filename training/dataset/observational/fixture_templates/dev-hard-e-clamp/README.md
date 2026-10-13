# DEV TASK: dev-hard-e-clamp
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: clamp(x, lo, hi) for integers.
- If lo > hi, raise ValueError. Do not swap the ends.
- Otherwise return x limited to the inclusive span [lo, hi].
- clamp(5, 0, 10) is 5
- clamp(0, 0, 10) is 0
- clamp(10, 0, 10) is 10
- clamp(-3, 0, 10) is 0
- clamp(1, 5, 1) raises ValueError

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
