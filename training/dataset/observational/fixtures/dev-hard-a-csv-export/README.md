# DEV TASK: dev-hard-a-csv-export
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #440).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: The order export is missing cells. Every column in the header must appear on every row. Numeric 0 and empty strings are real values and must be kept. A field that contains a comma or a double quote must be quoted, with internal quotes doubled.

Examples for columns sku, qty, note:
- sku=a, qty=0, note="" → a line "a,0,"
- sku=a, qty=1, note="red, blue" → the note is quoted
- sku=a, qty=2, note='say "hi"' → the note is quoted and the quote is doubled

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
