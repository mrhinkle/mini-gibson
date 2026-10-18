# Mini-Gibson v2 final-loop evidence

This directory is the public-safe evidence package for the preregistered Mini-Gibson v2 final loop. It is updated only from verified remote receipts and frozen repository inputs.

The reporting deadline is `2026-10-18 07:00 America/New_York`. The experiment reached a terminal qualification failure at `2026-10-18T03:18:02Z`, before training or model evaluation.

## Claim boundary

- Formal v2 efficacy decisions are permitted only at cumulative development `N=144`, `N=288`, or `N=432`.
- The required observed uplift is at least five percentage points, together with the frozen exact paired McNemar local alpha and safety gates.
- Operational progress, qualification receipts, training loss, pilot results, and between-look outcomes are not confirmatory efficacy evidence.
- The 35-task Gibson Bench v0.1 final holdout remains sealed unless every development promotion gate passes.
- Docker credentials, private registry configuration, container layers, model weights, and raw environment dumps are excluded. This package records only public-safe hashes and archive receipts for those objects.

## Files

- `REPORT.md` — human-readable finding and decision boundary.
- `summary.json` — machine-readable current conclusion.
- `LIMITATIONS.md` — precise scope limits and the safe next experiment boundary.
- `cost.json` — bounded runtime and cost estimate.
- `qualification/progress-snapshot.json` — final preparation and qualification checkpoint.
- `qualification/qualification.jsonl` — public-safe hash-chained header and terminal receipt.
- `qualification/terminal-result.json` — compact machine-readable terminal boundary.
- `verify_evidence.py` — hash and receipt verification.
- `SHA256SUMS` — hashes of every frozen public-safe package file except the manifest itself.

From the repository root, verify the frozen package with:

```sh
python3 docs/evidence/mini-gibson-v2-2026-10-18/verify_evidence.py
```

The complete pre-v2 status report remains at `docs/evidence/mini-gibson-final-loop-2026-10-17.md`.
