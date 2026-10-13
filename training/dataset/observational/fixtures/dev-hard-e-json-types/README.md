# DEV TASK: dev-hard-e-json-types
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: dump_obj(obj) returns a JSON object string.
- strings stay strings
- ints stay JSON numbers
- true and false stay JSON booleans, not the strings "true" and "false"
- None becomes JSON null, not the string "null"

dump_obj({"name": "a"}) is a JSON object with name "a".
dump_obj({"n": 2, "ok": True, "note": None}) loads back with int 2, bool True, and None.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
