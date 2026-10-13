# DEV TASK: dev-hard-a-tenant-cache
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #440).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: Cached values must be isolated by tenant and name. Setting a name for tenant A must not change tenant B. A missing entry returns None.

Examples:
- set("a", "color", "red"), set("b", "color", "blue") → get("a", "color") is "red" and get("b", "color") is "blue"
- get("a", "missing") is None

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
