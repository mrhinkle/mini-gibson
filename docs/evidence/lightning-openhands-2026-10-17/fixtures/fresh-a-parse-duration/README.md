# Parse human durations

`parse_duration()` should accept a non-negative decimal number followed by `ms`, `s`, `m`, or `h`, with optional surrounding whitespace, and return seconds as a float. Units are case-insensitive. Reject malformed, negative, or non-string inputs with `ValueError`.

Only `duration.py` may be changed.
