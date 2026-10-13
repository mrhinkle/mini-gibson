# DEV TASK: dev-hard-c-feature-gate
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #442).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: feature_enabled(file_on, env_value, user, deny) is True only when all of these hold:
- file_on is true
- env_value is not the string "0" (None and "1" are fine)
- user is not in deny

Otherwise False.
- file on, env None, user "ada", deny empty → True
- file on, env "0", user "ada", deny empty → False
- file on, env None, user "ada", deny {"ada"} → False
- file off, env "1", user "ada", deny empty → False
- file on, env "1", user "ada", deny {"bob"} → True

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
