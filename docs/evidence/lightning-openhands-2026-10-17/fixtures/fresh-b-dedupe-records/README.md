# Deduplicate records by normalized email

`dedupe_records(records)` returns copies of the first record for each email,
preserving order. Compare email values after stripping surrounding whitespace
and applying Unicode-aware `casefold()`. Do not rewrite the retained record's
email and do not mutate the input records.

Change only `dedupe_records.py`. Run `python3 -m unittest discover -s tests -q`.
