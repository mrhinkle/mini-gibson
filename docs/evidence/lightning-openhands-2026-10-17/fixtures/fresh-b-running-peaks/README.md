# Handle negative running peaks

`running_peaks(values)` returns the maximum value seen at each input position.
It must work for all integers, including all-negative sequences, preserve the
input length, and return an empty list for empty input.

Change only `running_peaks.py`. Run `python3 -m unittest discover -s tests -q`.
