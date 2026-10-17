# Validate bracket nesting order

`brackets_balanced(text)` returns whether `()`, `[]`, and `{}` brackets are
properly nested. Ignore all non-bracket characters. Matching totals are not
enough: a closer must match the most recent unmatched opener.

Change only `balanced_brackets.py`. Run `python3 -m unittest discover -s tests -q`.
