# Flight Recorder

Capture every Gibson agent run with its tool calls and the harness's own verdicts. It's the training and eval data for Mini Gibson, and the raw material for the self-learning loops.

- **[EPIC.md](EPIC.md):** why we need it, the deadline (capture live Mon Oct 5, window through Oct 14), the DAG, and the non-negotiables.
- **[issues/](issues/):** six child issues in the Gibson issue format (contract, area, out of scope, dependencies, tier). #1–#3 are P0.
- **[draft/](draft/):** starting code for each child:
  - `trace.sh`: a runner-capture library for `loop.sh` (claude stream-json, codex `--json`, grok session snapshot), plus run records and premature-completion labels
  - `trace-scrub.sh`: gitleaks fail-closed scrubbing, regex redaction, quarantine
  - `session-end-hook.sh`: captures interactive Claude Code sessions
  - `run-record.v1.schema.json`: the record schema
  - `trace_export.py`: exports clean traces to chat-format JSONL with normalized tools, a time split, and a frozen held-out set
- **[file-issues.sh](file-issues.sh):** files everything on GitHub with labels (`DRY_RUN=1` to preview).

Tests: `python -m unittest discover -s hackathon/flight-recorder/tests` (11 tests: export, labels, the held-out freeze, byte-identical runner handoff, the worktree guard, the kill switch, scrub redaction, quarantine, and fail-closed without gitleaks).

**Verify before merge:** the CLI flags marked `VERIFY` in `trace.sh`. Check `claude --help`, `codex exec --help`, and `grok --help` on the loop host, and commit one real event fixture per vendor. The Codex event shapes in the converter are a best guess until then.
