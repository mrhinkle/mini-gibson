# Keep the final partial chunk

`chunk_list(items, size)` returns a new list of consecutive list chunks of at
most `size` elements. The final partial chunk must be retained. An empty input
returns an empty list. A non-positive size raises `ValueError`.

Change only `chunk_list.py`. Run `python3 -m unittest discover -s tests -q`.
