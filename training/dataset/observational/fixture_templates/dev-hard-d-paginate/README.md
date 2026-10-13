# DEV TASK: dev-hard-d-paginate
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: page(items, page, size) is 1-based. Page 1 is the first size items. The slice length is size, except the last page which may be shorter. Page 0 or a size below 1 raises ValueError. A page past the end is an empty list.

Examples on ["a","b","c","d"]:
- page 1 size 2 → ["a", "b"]
- page 2 size 2 → ["c", "d"]
- page 3 size 2 → []
- page 1 size 3 → ["a", "b", "c"]

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
