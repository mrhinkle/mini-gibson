# DEV TASK: dev-hard-e-parse-date
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: parse_date(s) returns a datetime.date.
- "2020-01-02" → 2020-01-02
- "2020-01-02T03:04:05" → the date part, 2020-01-02
- "01/02/2020" is month/day/year → 2020-01-02
- "2020-13-01" and "13/40/2020" raise ValueError

The ISO date example working is not the whole contract.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
