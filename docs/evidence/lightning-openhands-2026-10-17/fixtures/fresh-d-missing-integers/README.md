# Find gaps between integers

`missing_integers(values)` returns every absent integer strictly between the
minimum and maximum input values, sorted ascending. Duplicates are ignored;
empty and single-value inputs return `[]`. Every value must be an actual integer,
not a boolean, or `ValueError` is raised.

Change only `gaps.py`. Run `python3 -m unittest discover -s tests -q`.
