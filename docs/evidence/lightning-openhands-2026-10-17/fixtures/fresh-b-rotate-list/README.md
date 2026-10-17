# Normalize list rotation steps

`rotate_right(items, steps)` returns a new list rotated to the right by
`steps`. Steps may be larger than the list or negative; normalize them by the
list length. An empty list returns an empty list for any step count. Do not
mutate the input.

Change only `rotate_list.py`. Run `python3 -m unittest discover -s tests -q`.
