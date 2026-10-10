# Outcome backfill: review verdicts, merge, fix-follow within 7 days

Labels: `gibson`, `tier-a`, `P1`, `area:observability`
Part of the flight-recorder epic. **Blocked by #2.**

## Sprint contract (acceptance criteria)
- [ ] AC1 — Daily job reads `clean/**/record.json` with a `pr` and adds `labels.outcome`: `review_verdicts[]` (from `pr-review-evidence`: reviewer vendor, E-level, verdict, exact-head sha), `merged` (bool + sha), `closed_unmerged` (bool).
- [ ] AC2 — `labels.outcome.fix_follow`: true if a PR merged within 7 days touches the same files and references the original PR or issue. Computed once the 7 days have elapsed, and null before then.
- [ ] AC3 — Backfill is additive. It never rewrites `labels.harness` and records `backfilled_at`.

## Dependencies
Blocked by #2.

## Tier
A.
