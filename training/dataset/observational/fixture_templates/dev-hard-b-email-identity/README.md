# DEV TASK: dev-hard-b-email-identity
Split: DEV_OBSERVATIONAL (synthetic fixture, issue #441).
This is not a SWE-rebench task, a Gibson temporal holdout, or a Mini Gibson final-eval task.

Goal: Adding a user normalizes the email and rejects duplicates and junk.
- Trim surrounding spaces and lowercase the address before it is stored.
- The stored value is that normalized address.
- A second add of the same mailbox, even if the new text differs by case or surrounding spaces, raises ValueError("duplicate").
- An empty address, or one without @, raises ValueError("bad email").

Examples:
- add(" A@B.com ") returns "a@b.com"
- add("a@b.com") after that raises duplicate
- add("  ") and add("not-an-email") raise bad email

Do not edit test files. Verification seals them.
Run: python3 -m unittest discover -s . -p 'test_*.py' -q && bash seal_tests.sh
