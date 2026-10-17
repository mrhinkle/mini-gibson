# Safely redact a token

`redact_token(token, visible=4)` must replace the hidden prefix with `*` while retaining the final `visible` characters. If a token is no longer than `visible`, redact the entire token. A visible count of zero redacts everything. Reject non-string tokens and negative/non-integer visible counts with `ValueError`.

Only `redact.py` may be changed.
