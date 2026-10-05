#!/usr/bin/env python3
"""Validate runs.jsonl against schema.observational.v0.1.json (+ light invariants)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

OBS_ROOT_DEFAULT = Path(__file__).resolve().parents[1]  # .../training/dataset/observational
REPO_ROOT = OBS_ROOT_DEFAULT.parents[2]
DEFAULT_OBS = OBS_ROOT_DEFAULT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--runs",
        type=Path,
        default=DEFAULT_OBS / "runs.jsonl",
        help="JSONL path (default OBS runs.jsonl)",
    )
    ap.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_OBS / "schema.observational.v0.1.json",
    )
    ap.add_argument("--sample-ok", action="store_true", help="allow runs.sample.jsonl")
    args = ap.parse_args()

    if not args.runs.exists():
        print(f"MISSING {args.runs}", file=sys.stderr)
        return 2
    schema = json.loads(args.schema.read_text())
    required = schema["required"]
    allowed_terminal = set(schema["properties"]["terminal_outcome"]["enum"])
    allowed_labels = set(schema["properties"]["failure_labels"]["items"]["enum"])
    model_const = schema["properties"]["model"].get("const")
    split_const = schema["properties"]["split"].get("const")

    errors = []
    rows = []
    for i, line in enumerate(args.runs.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"L{i}: JSON {e}")
            continue
        rows.append(row)
        for k in required:
            if k not in row:
                errors.append(f"L{i} {row.get('run_id')}: missing {k}")
        if model_const and row.get("model") != model_const:
            errors.append(f"L{i}: model {row.get('model')} != {model_const}")
        if split_const and row.get("split") != split_const:
            # expansion may introduce TEST_OBSERVATIONAL — warn only if not sample
            if row.get("split") not in (
                "DEV_OBSERVATIONAL",
                "TEST_OBSERVATIONAL",
            ):
                errors.append(f"L{i}: bad split {row.get('split')}")
        if row.get("terminal_outcome") not in allowed_terminal:
            errors.append(f"L{i}: bad terminal_outcome")
        for lab in row.get("failure_labels") or []:
            if lab not in allowed_labels:
                errors.append(f"L{i}: bad failure_label {lab}")
        if not row.get("provider"):
            errors.append(f"L{i}: empty provider")
        # claim-only investigate soft flag
        if row.get("verifier_outcome") == "claim_based_investigate" and row.get(
            "terminal_outcome"
        ) == "verified":
            pass  # counted in summary

    print(f"rows={len(rows)} errors={len(errors)}")
    print("terminal", Counter(r.get("terminal_outcome") for r in rows))
    print("verifier", Counter(r.get("verifier_outcome") for r in rows))
    print("provider", Counter(r.get("provider") for r in rows))
    print(
        "failure_labels",
        Counter(l for r in rows for l in (r.get("failure_labels") or [])),
    )
    costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    if costs:
        print(f"cost_sum_usd={sum(costs):.6f} n_cost={len(costs)}")
    claim_only = sum(
        1
        for r in rows
        if r.get("verifier_outcome") == "claim_based_investigate"
        and r.get("terminal_outcome") == "verified"
    )
    print(f"claim_based_investigate_verified={claim_only}")
    for e in errors[:40]:
        print("ERR", e)
    if errors:
        print(f"... total errors {len(errors)}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
