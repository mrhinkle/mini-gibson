# DEV TASK: dev-hard-e-url-join
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #444).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: join_url(base, path) joins with exactly one slash and keeps a query string on the path.
- join_url("https://ex.com", "a") → "https://ex.com/a"
- join_url("https://ex.com/", "a") → "https://ex.com/a"
- join_url("https://ex.com/a", "b?x=1") → "https://ex.com/a/b?x=1"
- join_url("https://ex.com/a/", "/b") → "https://ex.com/a/b"
An empty path returns base unchanged.

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
