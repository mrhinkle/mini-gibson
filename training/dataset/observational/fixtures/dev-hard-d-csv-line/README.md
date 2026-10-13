# DEV TASK: dev-hard-d-csv-line
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: parse_csv_line(line) splits one CSV record.
- "a,b,c" → ["a", "b", "c"]
- a quoted field may contain commas: 'a,"b,c",d' → ["a", "b,c", "d"]
- a doubled quote inside a quoted field is one quote character. The record a, then a quoted say-"hi", then b parses as three fields: a, say "hi", and b.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
