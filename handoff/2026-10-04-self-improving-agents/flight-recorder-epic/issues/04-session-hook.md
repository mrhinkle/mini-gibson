# SessionEnd hook: capture interactive Claude Code sessions

Labels: `gibson`, `tier-b`, `P1`, `area:loop`
Part of the flight-recorder epic. **Blocked by #3.**

## Goal
Mark's own interactive Claude Code sessions are some of the richest runs. Capture them into the same store, without depending on the protected `~/.claude/projects` folder being exported by hand.

## Sprint contract (acceptance criteria)
- [ ] AC1 — A `SessionEnd` hook (user-level `~/.claude/settings.json`, documented in `adapters/claude-code/README.md`) reads the hook JSON from stdin and copies `transcript_path` into `raw/<repo>/<date>/<session_id>/events.claude-session.jsonl`, plus a minimal `record.json` (`role: "interactive"`, `cwd`, repo from `git -C cwd remote get-url origin` if any).
- [ ] AC2 — It runs `trace-scrub.sh` on the new run dir before exiting.
- [ ] AC3 — Hook failures never block session exit (exit 0 always; errors to `~/gibson-traces/hook-errors.log`).
- [ ] AC4 — Opt-out: the hook skips any session whose cwd is outside `~/Code/` or matches `GIBSON_TRACE_EXCLUDE` globs (personal and non-dev sessions are never captured).

## Affected area
`adapters/claude-code/README.md`, new `adapters/claude-code/session-end-hook.sh`, tests.

## Dependencies
Blocked by #3.

## Tier
B. Draft: `draft/session-end-hook.sh`.
