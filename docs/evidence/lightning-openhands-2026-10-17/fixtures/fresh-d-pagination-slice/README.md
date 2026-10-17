# Fix one-based pagination

`page_slice(items, page, page_size)` returns a new list for the requested
one-based page. A page beyond the available items returns `[]`. `page` and
`page_size` must be positive integers; booleans and other values raise
`ValueError`. Do not mutate the input.

Change only `pagination.py`. Run `python3 -m unittest discover -s tests -q`.
