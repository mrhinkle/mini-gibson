# DEV TASK: dev-hard-b-form-errors
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: handle(form) validates name and email.
- Missing or blank name, or missing or blank email, is a 400 whose errors include "required".
- An email without @ is a 400 whose errors include "format" (that exact code).
- A form with both a non-blank name and an email containing @ is 200 and {"ok": True}.

The HTTP status has to follow the validator's codes. A format error is not a success.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
