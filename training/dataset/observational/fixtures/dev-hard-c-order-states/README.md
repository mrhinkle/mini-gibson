# DEV TASK: dev-hard-c-order-states
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: can_transition(src, dst) is true only for these edges:
- draft → submitted
- submitted → paid
- submitted → draft
- paid → shipped
Every other pair is false, including draft → shipped, shipped → paid, and paid → draft.
Same-state moves are false.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
