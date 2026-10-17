# Interleave uneven iterables

`round_robin(*iterables)` returns a list taking one item from each iterable in
turn until all are exhausted. Longer iterables continue after shorter ones end,
falsey values are retained, and one-shot iterators must work.

Change only `interleave.py`. Run `python3 -m unittest discover -s tests -q`.
