#!/usr/bin/env python3
"""Verify the public-safe Mini-Gibson v2 evidence package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.verify_rebench import verify_receipt  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    manifest = ROOT / "SHA256SUMS"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"hash mismatch: {relative}")

    journal = ROOT / "qualification" / "qualification.jsonl"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 2 or rows[1]["record_sha256"] != "65dfff54b91464f8f1340357e40e4eba5db2609a643d587c9b1f91a8fdf69cd5":
        raise SystemExit("unexpected qualification journal boundary")
    if not verify_receipt(rows[1]["receipt"]) or rows[1]["receipt"]["qualified"]:
        raise SystemExit("terminal receipt semantics failed verification")

    summary = json.loads((ROOT / "summary.json").read_text(encoding="utf-8"))
    if summary["v2"]["formal_development_n"] != 0:
        raise SystemExit("formal-look boundary changed")
    if summary["v2"]["final_holdout"] != "sealed_unconsumed":
        raise SystemExit("final holdout boundary changed")
    print("evidence verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
