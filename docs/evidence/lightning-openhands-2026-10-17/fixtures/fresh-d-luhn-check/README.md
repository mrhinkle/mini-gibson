# Validate Luhn checksums

`luhn_valid(number)` accepts a string containing digits with optional ASCII
spaces or hyphens and returns whether its Luhn checksum is valid. Separators are
ignored, but all other characters, an empty digit sequence, and a single digit
are invalid and return `False`.

Change only `luhn.py`. Run `python3 -m unittest discover -s tests -q`.
