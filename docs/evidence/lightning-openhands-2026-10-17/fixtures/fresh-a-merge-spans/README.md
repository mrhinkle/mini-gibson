# Merge inclusive spans

`merge_spans(spans)` must normalize unsorted inclusive integer `(start, end)` spans by merging overlaps and touching boundaries. Return sorted tuples and do not mutate the input. Raise `ValueError` when a start is greater than its end.

Only `spans.py` may be changed.
