# Sort strict numeric versions

`sort_versions(versions)` returns the input strings ordered by numeric
`MAJOR.MINOR.PATCH` components while preserving duplicate values. Each version
must contain exactly three non-negative decimal integer components; malformed
values raise `ValueError`. Do not mutate the input.

Change only `versions.py`. Run `python3 -m unittest discover -s tests -q`.
