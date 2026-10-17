# Immutably update a nested dictionary

`set_in_copy(data, path, value)` returns a dictionary with `value` stored at a non-empty sequence of non-empty string keys. Existing nested dictionaries must not be mutated, missing dictionaries are created, and traversing through a non-dictionary raises `TypeError`. Invalid `data` or paths raise `ValueError`.

Change only `nested.py`. Run `python3 -m unittest discover -s tests -q`.
