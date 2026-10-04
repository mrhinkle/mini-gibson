# Training export: normalized tool calls, time-split, held-out freeze

Labels: `gibson`, `tier-a`, `P1`, `area:research`
Part of the flight-recorder epic. **Blocked by #2 and #3.**

## Sprint contract (acceptance criteria)
- [ ] AC1 — `scripts/trace-export.py` reads **only** `clean/` and emits chat-format JSONL (`messages` with `tool_calls` and `tool` results) that vLLM and Nemotron's chat template accept.
- [ ] AC2 — Vendor tools are normalized to one tool set: `read_file`, `write_file`, `edit_file`, `run_command`, `search`, plus `other:<name>` passthrough. The mapping is a versioned table in the script.
- [ ] AC3 — Time split: runs started before `--cutoff` go to train; runs after go to held-out. `--freeze` writes `heldout.manifest.json` with run_ids and sha256s, and later exports refuse to put a frozen run in train.
- [ ] AC4 — Filters: `--only-verified` keeps runs whose `labels.harness.gate_exit == 0` and with no test-integrity failure (positives). `--premature` emits `claimed_status == success && gate_exit != 0` runs as labeled negatives.
- [ ] AC5 — Summary report: counts by repo, runner, role, label, and premature-completion rate.

## Dependencies
Blocked by #2 and #3.

## Tier
A. Draft: `draft/trace_export.py` (with tests).
