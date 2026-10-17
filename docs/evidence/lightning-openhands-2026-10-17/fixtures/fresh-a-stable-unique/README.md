# Keep the first record per key

`stable_unique_by(records, key)` should return records in input order while retaining only the first record for each distinct `record[key]`. It must not mutate the records or input iterable. Missing keys should naturally raise `KeyError`.

Only `records.py` may be changed.
