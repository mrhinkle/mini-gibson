# Count half-open event concurrency

`max_concurrent(events)` returns the greatest number of overlapping half-open
integer intervals `(start, end)`. An interval ending when another starts does
not overlap it. Require `start < end` for every interval or raise `ValueError`;
an empty input returns `0`.

Change only `concurrency.py`. Run `python3 -m unittest discover -s tests -q`.
