# Flatten a nested mapping

`flatten_mapping(mapping, sep=".")` recursively flattens nested dictionaries into joined key paths. Keys and `sep` must be non-empty strings; invalid values raise `ValueError`. Empty dictionaries contribute no entry. A collision between two flattened paths raises `ValueError`, and the input must not be mutated.

Change only `flatten.py`. Run `python3 -m unittest discover -s tests -q`.
