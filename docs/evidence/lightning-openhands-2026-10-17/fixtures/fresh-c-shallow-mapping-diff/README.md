# Diff two mappings shallowly

`mapping_diff(before, after)` returns `{"added": ..., "removed": ..., "changed": ...}`. Added values come from `after`, removed values from `before`, and changed entries map each key to `(before_value, after_value)`. Compare values shallowly with `==`; omit unchanged keys. Each section's string keys must be inserted in sorted order. Inputs must be mappings with string keys, must not be mutated, and invalid input raises `ValueError`.

Change only `mapping_diff.py`. Run `python3 -m unittest discover -s tests -q`.
