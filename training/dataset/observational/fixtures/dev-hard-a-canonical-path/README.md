# DEV TASK: dev-hard-a-canonical-path
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #440).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: Redirect targets are built from request paths, and two URLs that should be the same page stay distinct. The public canonicalizer must:
- percent-decode once
- lowercase
- turn spaces and underscores into hyphens
- collapse repeated hyphens
- ensure a single leading slash
- drop a trailing slash except for the root path

Examples:
- "/Hello World" → "/hello-world"
- "/Hello%20World" → "/hello-world"
- "A__B/" → "/a-b"
- "/already" → "/already"

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
