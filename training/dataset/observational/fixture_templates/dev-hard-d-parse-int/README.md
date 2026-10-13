# DEV TASK: dev-hard-d-parse-int
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: parse_int(s) reads one base-10 integer.
- Surrounding spaces are ignored. " 42 " is 42.
- A leading + is allowed. "+42" is 42.
- A leading - is allowed. "-7" is -7.
- Empty input, or any character that is not part of that optional sign plus digits, raises ValueError.
- "42abc" raises ValueError. It is not 42 and it is not 0.

The public function is nums.parse_int.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
