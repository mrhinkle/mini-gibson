# Format a byte count with binary units

`format_bytes(size)` formats a non-negative integer byte count using `B`, `KiB`, `MiB`, `GiB`, or `TiB`. Byte values have no decimal; larger units always have one decimal. Choose the largest unit whose size does not exceed the value, capped at `TiB` (for example, `1536` becomes `"1.5 KiB"`). Booleans and non-integers are invalid. Invalid input raises `ValueError`.

Change only `byte_size.py`. Run `python3 -m unittest discover -s tests -q`.
