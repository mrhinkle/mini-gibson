# Group consecutive equal values

`group_runs(values)` returns `(value, count)` tuples for consecutive equal runs, preserving encounter order. Equal values separated by another value belong to different runs. The function must support one-shot iterables and unhashable or unsortable values, and empty input returns `[]`.

Change only `runs.py`. Run `python3 -m unittest discover -s tests -q`.
