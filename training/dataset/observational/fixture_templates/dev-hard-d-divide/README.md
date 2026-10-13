# DEV TASK: dev-hard-d-divide
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: divide(a, b) is true division, not integer truncation.
- divide(7, 2) is 3.5
- divide(-4, 2) is -2
- divide(1, 0) raises ValueError whose message contains "division by zero"
- It must not return None

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
