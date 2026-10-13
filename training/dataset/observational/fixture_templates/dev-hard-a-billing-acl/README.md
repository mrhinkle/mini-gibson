# DEV TASK: dev-hard-a-billing-acl
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #440).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: Account roles arrive as lowercase "admin" or "member". An admin may "billing" and "read". A member may "read" only. Any other role or action is denied.

Examples:
- admin, billing → allowed
- admin, read → allowed
- member, read → allowed
- member, billing → denied
- guest, read → denied

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
