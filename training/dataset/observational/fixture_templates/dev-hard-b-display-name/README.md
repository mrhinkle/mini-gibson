# DEV TASK: dev-hard-b-display-name
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: Records have a legacy "name" and a newer "display_name".
- display(record) returns display_name when it is a non-empty string, otherwise name.
- write_record(name) stores both display_name and name set to that name, so a legacy reader still sees name.
- A record that has both prefers display_name.

Examples:
- {"name": "Ada"} displays "Ada"
- {"display_name": "Grace", "name": "Old"} displays "Grace"
- write_record("Ada")["name"] == "Ada" and display of that record is "Ada"

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
