# Run record + harness-sensor labels per run

Labels: `gibson`, `tier-b`, `P0`, `area:loop`
Part of the flight-recorder epic. **Blocked by #1.**

## Goal
Each runner invocation gets a `record.json` that ties the trace to the task, the code, and the harness's own verdict.

## Sprint contract (acceptance criteria)
- [ ] AC1 — `record.json` validates against `run-record.v1.schema.json` (draft provided) and includes: `run_id`, `repo`, `issue`, `pr` (if any), `lane`, `role` (builder/reviewer/repair/release), `runner`, `model` (if knowable), `prompt_sha256`, `base_sha`, `head_sha_start`, `head_sha_end`, `started_at`, `ended_at`, `exit_code`, `timed_out`, `trace_mode`, `trace_status`.
- [ ] AC2 — `labels.harness` is populated at run end **from existing sensors only**: gate exit code (`gate.sh`), `test-integrity.mjs` result, and `truthful-status.mjs` run with the agent's claimed status vs. the gate exit. Each label records the sensor name, version (script sha256), and raw exit code.
- [ ] AC3 — `labels.claimed_status` is set to `success | partial | blocked | none`, derived from the final text by the same rule `truthful-status` uses, so the premature-completion label is `claimed_status == success && gate_exit != 0`.
- [ ] AC4 — Cost fields are filled from `cost-ledger.sh` when available, else null (never estimated).
- [ ] AC5 — A run that times out still writes a record with `timed_out: true` and whatever events were captured.

## Affected area
`scripts/lib/trace.sh`, `scripts/loop.sh` (end-of-iteration hook), `config/run-record.v1.schema.json`, tests.

## Out of scope
Labels that arrive later: review verdicts, merges, fix-follow (#5).

## Dependencies
Blocked by #1.

## Tier
B. Draft: `draft/run-record.v1.schema.json`, `draft/trace.sh` (`trace_end`).
