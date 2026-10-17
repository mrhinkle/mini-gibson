# Parse one CSV record correctly

`parse_csv_record(text)` returns the fields in exactly one comma-delimited CSV
record. Honor quoted commas, doubled quotes, and empty fields. Embedded or
trailing record separators and malformed quoting raise `ValueError`.

Change only `csv_record.py`. Run `python3 -m unittest discover -s tests -q`.
