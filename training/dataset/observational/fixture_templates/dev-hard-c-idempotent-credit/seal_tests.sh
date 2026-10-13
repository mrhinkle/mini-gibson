#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 - << 'PY'
import hashlib, pathlib, sys
root = pathlib.Path(".")
files = sorted(p for p in root.rglob("test*.py") if p.is_file())
h = hashlib.sha256()
for p in files:
    h.update(str(p).encode())
    h.update(b"\0")
    h.update(p.read_bytes())
expected = pathlib.Path(".test_seal").read_text().strip()
got = h.hexdigest()
if got != expected:
    print(f"test seal mismatch", file=sys.stderr)
    raise SystemExit(1)
PY
