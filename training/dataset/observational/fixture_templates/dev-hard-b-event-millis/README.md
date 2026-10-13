# DEV TASK: dev-hard-b-event-millis
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: The event payload field "ts" is a unix timestamp in milliseconds.
- emit(kind, ts_ms) stores that millisecond value on "ts"
- read_event(payload) returns ts_ms equal to the stored "ts", without scaling
- A payload that already holds milliseconds must read back as those same milliseconds
- Round-tripping emit then read_event returns the original millisecond value

Example: emit("ping", 1700000000123) then read_event yields ts_ms 1700000000123.
A hand-built {"kind": "x", "ts": 1700000000000} reads back as 1700000000000.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
