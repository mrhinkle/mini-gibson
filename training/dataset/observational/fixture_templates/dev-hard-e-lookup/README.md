# DEV TASK: dev-hard-e-lookup
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: lookup(rows, id_) finds a row by its id.
- Surrounding spaces on the query id are stripped before the compare.
- A hit returns that row.
- An unknown id raises KeyError.
- A blank id after stripping raises ValueError.
- Do not return None for a miss.

Rows look like {"id": "ada", "name": "Ada"}.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
