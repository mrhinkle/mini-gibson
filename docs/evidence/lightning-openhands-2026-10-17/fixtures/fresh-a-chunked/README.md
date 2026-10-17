# Chunk any iterable

`chunked(iterable, size)` must yield lists of at most `size` items without dropping a final partial chunk. It must work with one-shot generators. Reject non-integer and non-positive sizes with `ValueError`.

Only `chunks.py` may be changed.
