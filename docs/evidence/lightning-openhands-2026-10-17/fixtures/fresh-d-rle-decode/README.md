# Validate run-length decoding

`decode_runs(runs)` expands `(value, count)` pairs in encounter order. Every
count must be a positive integer; booleans, zero, negatives, and non-integers
raise `ValueError`. An empty input returns `[]`.

Change only `run_length.py`. Run `python3 -m unittest discover -s tests -q`.
