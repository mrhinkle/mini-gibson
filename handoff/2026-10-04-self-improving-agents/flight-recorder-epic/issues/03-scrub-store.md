# Scrub-on-ingest + private append-only trace store

Labels: `gibson`, `tier-c`, `P0`, `area:security`
Part of the flight-recorder epic. **Lands first; blocks #1 and #4.**

## Goal
Raw agent traces contain API keys, tokens, env values, private paths, and sometimes attendee PII. Make sure they only ever land in a private store, and that only scrubbed copies can be exported.

## Sprint contract (acceptance criteria)
- [ ] AC1 — Store root is `$GIBSON_TRACE_ROOT` (default `~/gibson-traces`). It must resolve **outside** every git worktree; `trace.sh` refuses to write if `git -C "$root" rev-parse` succeeds. The directory is mode 0700.
- [ ] AC2 — Layout: `raw/<repo>/<YYYY-MM-DD>/<run_id>/` and `clean/<repo>/<YYYY-MM-DD>/<run_id>/`. Run dirs are append-only once sealed, and a per-day `SHA256SUMS` covers sealed files.
- [ ] AC3 — `scripts/trace-scrub.sh <raw_run_dir>` writes the clean copy: (a) `gitleaks detect --no-git` over every file, failing closed (any finding → the run is quarantined to `quarantine/`, not cleaned); (b) regex redaction of home paths, emails, bearer tokens, `*_API_KEY=`/`*_TOKEN=` values, and connection strings; (c) existing `scripts/injection-scan.sh` flags recorded in `record.json` (flagged, not dropped).
- [ ] AC4 — Raw retention: `raw/` older than 30 days is deleted by a scheduled job. `clean/` is kept.
- [ ] AC5 — Nightly sync of `clean/` only to a private destination (private repo or bucket). `raw/` never leaves the host.
- [ ] AC6 — Adversarial test: a fixture trace with a planted fake key, a home path, and an email produces a clean copy that contains none of them, or a quarantine. Red-team note in `playbooks/red-team/`.

## Affected area
New `scripts/trace-scrub.sh`, `scripts/lib/trace.sh` (root guard), scheduled job (launchd plist alongside the existing loop plist), `playbooks/red-team/trace-scrub.md`, tests.

## Out of scope
Deciding what goes to Hugging Face (that's a manual, owner-gated step on the exported dataset).

## Dependencies
None.

## Tier
**C** (secrets and PII boundary). E3 cross-vendor review plus the owner's merge. Draft: `draft/trace-scrub.sh`.
