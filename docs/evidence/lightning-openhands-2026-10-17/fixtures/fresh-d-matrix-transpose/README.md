# Reject ragged matrix transposition

`transpose(matrix)` returns the row/column transpose as lists. `[]` returns
`[]`, and a matrix of empty rows also returns `[]`. All rows must have equal
length; a ragged matrix raises `ValueError`. Do not mutate the matrix.

Change only `matrix.py`. Run `python3 -m unittest discover -s tests -q`.
