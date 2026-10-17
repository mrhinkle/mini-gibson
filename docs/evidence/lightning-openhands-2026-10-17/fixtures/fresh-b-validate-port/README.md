# Reject boolean port values

`validate_port(value)` returns a valid TCP/UDP port unchanged. A valid value is
an actual integer from 1 through 65535 inclusive. Strings, floats, booleans,
and other types must raise `TypeError`; out-of-range integers must raise
`ValueError`.

Change only `validate_port.py`. Run `python3 -m unittest discover -s tests -q`.
