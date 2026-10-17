# Count values in boundary buckets

`histogram(values, boundaries)` returns `len(boundaries) + 1` counts. For boundaries `[b0, b1]`, buckets are `(-inf, b0]`, `(b0, b1]`, and `(b1, inf)`: a value equal to a boundary belongs to the lower bucket. Boundaries must be finite, strictly increasing numbers; values must be finite numbers. Booleans are not numbers here. Invalid input raises `ValueError`, and inputs are not mutated.

Change only `histogram.py`. Run `python3 -m unittest discover -s tests -q`.
