# Compress integer ranges

`compress_integers(values)` removes duplicates, sorts the integers, and formats consecutive runs as `start-end` with singleton values unchanged, joined by commas. Empty input returns `""`. Values must be actual integers (not booleans); otherwise raise `ValueError`.

Change only `ranges.py`. Run `python3 -m unittest discover -s tests -q`.
