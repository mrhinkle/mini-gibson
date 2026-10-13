# DEV TASK: dev-hard-d-phone
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #443).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: format_phone(s) returns E.164-style text.
- 10 digits (punctuation ignored) get a +1 prefix: "(555) 123-4567" and "5551234567" → "+15551234567"
- 11 digits that start with 1 get a + prefix and those digits: "15551234567" → "+15551234567"
- A value that already starts with + keeps the plus and the digits after it: "+44 20 7946 0958" → "+442079460958". Do not force those into +1.
- Anything else, including "123", raises ValueError.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
