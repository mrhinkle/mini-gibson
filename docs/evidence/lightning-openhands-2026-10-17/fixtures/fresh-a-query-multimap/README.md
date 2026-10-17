# Parse a query string into a multimap

`parse_query_multimap(query)` must accept a raw query string with an optional leading `?`. Return a dict mapping decoded keys to lists of decoded values in encounter order. Preserve duplicate keys and blank values, interpret `+` as space, and return `{}` for an empty query.

Only `query.py` may be changed.
