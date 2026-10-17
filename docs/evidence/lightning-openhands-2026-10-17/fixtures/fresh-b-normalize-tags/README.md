# Collapse whitespace while normalizing tags

`normalize_tags(tags)` strips surrounding whitespace, collapses every run of
internal whitespace to one ASCII space, applies Unicode-aware `casefold()`,
omits empty results, and removes duplicates while retaining first-seen order.

Change only `normalize_tags.py`. Run `python3 -m unittest discover -s tests -q`.
