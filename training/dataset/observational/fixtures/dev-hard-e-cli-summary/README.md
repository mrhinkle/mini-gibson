# DEV TASK: dev-hard-e-cli-summary
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: summarize(numbers) prints one line and returns 0.
The line is count=<n> total=<sum> with no extra text. n is how many numbers were passed. sum is their integer sum. An empty list is count=0 total=0.

Examples:
- summarize([2, 3]) prints "count=2 total=5" and returns 0
- summarize([]) prints "count=0 total=0" and returns 0
Exit status alone is not the contract. The line has to carry both numbers.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
