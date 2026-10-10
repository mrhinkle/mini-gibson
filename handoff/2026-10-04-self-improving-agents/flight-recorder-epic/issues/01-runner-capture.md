# Runner capture: structured output for claude/codex/grok, tee to trace

Labels: `gibson`, `tier-b`, `P0`, `area:loop`
Part of the flight-recorder epic. **Blocked by #3.**

## Goal
Record every tool call and observation from each runner invocation in `scripts/loop.sh` without changing what the loop receives.

## Sprint contract (acceptance criteria)
- [ ] AC1 — `claude` runner invokes `claude -p --output-format stream-json --verbose --permission-mode acceptEdits`; raw JSONL is teed to `$TRACE_DIR/events.claude.jsonl`; the text passed on to the loop equals the `result` field of the final `{"type":"result"}` event. *Verify the flags with `claude --help` on the loop host first.*
- [ ] AC2 — `codex` runner (builder and `REVIEWER_CMD`) invokes `codex exec --json …`; JSONL is teed to `events.codex.jsonl`; the final text is extracted from the last agent-message event. *Verify `--json` and the event names with `codex exec --help` and one real run, then commit a fixture.*
- [ ] AC3 — `grok` runner: if `grok --help` shows a JSON/stream output flag, use it as in AC1. Otherwise snapshot the newest session file under `~/.grok/` that was modified during the run window into `events.grok.raw`. Record which path was used in `trace_mode`.
- [ ] AC4 — Byte-identity test: on fixture runs, the text handed to the rest of `loop.sh` with capture on equals the text with capture off (`scripts/tests/trace-capture.test.sh`).
- [ ] AC5 — Capture failure (disk full, missing jq, unknown event shape) leaves the run's exit code and output unchanged and sets `trace_status: "failed"` with a reason.
- [ ] AC6 — `GIBSON_TRACE=0` disables capture entirely (kill switch), default on.
- [ ] AC7 — `second-opinion.sh` and `loop-fleet.sh` reviewer/release commands get the same capture (reviews are training data too).

## Affected area
`scripts/loop.sh` (runner block ~1985–2015), `scripts/loop-fleet.sh` (REVIEWER_CMD/RELEASE_CMD), `scripts/second-opinion.sh`, new `scripts/lib/trace.sh`, `scripts/tests/trace-capture.test.sh`.

## Out of scope
Scrubbing and storage (#3), labels (#2), interactive sessions (#4).

## Dependencies
Blocked by #3.

## Tier
B (shared module; touches every run). Draft: `draft/trace.sh`.
