# DEV TASK: dev-hard-a-report-window
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #440).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: The report labeled "last 7 days" is showing eight dates. It must be the inclusive range of today and the six days before it (7 dates), oldest first, as ISO dates. A fixed today of 2024-03-15 must produce 2024-03-09 through 2024-03-15.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
