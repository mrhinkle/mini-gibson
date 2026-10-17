# Fix inclusive date filtering

`dates_in_window(values, start, end)` accepts ISO `YYYY-MM-DD` strings and
returns the input values whose dates fall in the inclusive range from `start`
through `end`. Preserve input order and duplicates. Invalid ISO dates should
raise `ValueError`, as should a range whose start is after its end.

Change only `date_range.py`. Run `python3 -m unittest discover -s tests -q`.
