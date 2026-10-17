# Remove zero totals when merging counts

`merge_counts(*mappings)` returns a new dictionary containing the summed count
for every key across the input dictionaries. Keys whose final total is zero
must be omitted. Do not mutate any input dictionary.

Change only `merge_counts.py`. Run `python3 -m unittest discover -s tests -q`.
