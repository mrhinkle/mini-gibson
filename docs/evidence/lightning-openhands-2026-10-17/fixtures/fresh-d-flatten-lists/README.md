# Recursively flatten lists

`flatten_lists(values)` returns a new flat list by recursively expanding only
nested `list` instances. Non-list values, including tuples and strings, remain
atomic. Preserve left-to-right order and do not mutate the input.

Change only `flatten.py`. Run `python3 -m unittest discover -s tests -q`.
