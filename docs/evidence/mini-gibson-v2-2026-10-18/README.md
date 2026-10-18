# Mini-Gibson v2 final-loop evidence

This directory is the public-safe evidence package for the preregistered Mini-Gibson v2 final loop. It is updated only from verified remote receipts and frozen repository inputs.

The reporting deadline is `2026-10-18 07:00 America/New_York`. If the experiment has not reached a terminal preregistered decision by that cutoff, the package will contain a complete cutoff report rather than an invented model conclusion.

## Claim boundary

- Formal v2 efficacy decisions are permitted only at cumulative development `N=144`, `N=288`, or `N=432`.
- The required observed uplift is at least five percentage points, together with the frozen exact paired McNemar local alpha and safety gates.
- Operational progress, qualification receipts, training loss, pilot results, and between-look outcomes are not confirmatory efficacy evidence.
- The 35-task Gibson Bench v0.1 final holdout remains sealed unless every development promotion gate passes.
- Docker credentials, private registry configuration, container layers, model weights, and raw environment dumps are excluded. This package records only public-safe hashes and archive receipts for those objects.

## Files

- `REPORT.md` — human-readable finding and decision boundary.
- `summary.json` — machine-readable current conclusion.
- `qualification/progress-snapshot.json` — latest verified preparation and qualification checkpoint.
- `SHA256SUMS` — generated only when a report revision is frozen.

The complete pre-v2 status report remains at `docs/evidence/mini-gibson-final-loop-2026-10-17.md`.
