# EPIC: Flight recorder — capture every agent run with verdicts (P0)

Labels: `gibson`, `tier-c`, `P0`, `area:observability`
Tracking issue for #1–#6 below.

## Why
Every runner call in `scripts/loop.sh` uses text mode (`claude -p --output-format text`, line ~2003; plain `codex exec`, line ~2007; `grok --prompt-file`, line ~1997). Each run hands back one final paragraph, and every tool call, observation, and premature "done" is lost. Meanwhile the harness already computes the verdicts that matter: `truthful-status.mjs` (claimed vs. actual), `test-integrity.mjs`, gate exit codes, and review evidence. **We record the outcomes but throw away the runs.**

That blocks two things:
1. **Mini Gibson** (Red Hat × NVIDIA Small Models Hack, Oct 17–18) needs several hundred verified agent runs with their tool calls to train and evaluate the adapter. The git history has diffs but no runs.
2. **The self-learning loops** (docs/28, docs/09). Lessons today come from narrated incidents. With traces, a failure class can be counted, replayed, and regression-tested.

## Deadline
- **Capture live on all runners by Mon Oct 5 EOD** (#1, #2, #3).
- Capture window: Oct 5–14. Dataset freeze and held-out split: Oct 15. Hack: Oct 17–18.
- #4–#6 by Oct 13.

## DAG
```
#3 scrub + private store ──┬──> #1 runner capture ──> #2 run record + sensor labels ──> #5 outcome backfill
                           │                                                          └─> #6 training export
                           └──> #4 SessionEnd hook (interactive sessions)
```
Raw traces contain secrets and PII, so **#3 lands first**. No capture writes anywhere until the private store and scrub exist. That's also why the epic is Tier C.

## Non-negotiables
- Traces never go in the public Gibson repo or in any target repo. The raw store sits outside every git worktree, mode 0700.
- Only **scrubbed** traces are eligible for training or export. Raw is retained privately for 30 days, then deleted.
- Capture must not change runner behavior. The final-text handoff to the rest of the loop is byte-identical to today's (#1 AC).
- Capture failure never fails the run. It logs `trace_status=failed` in the record and moves on (Law 8: report it truthfully).

## Children
| # | Title | Tier | Priority |
|---|---|---|---|
| 1 | Runner capture: structured output for claude/codex/grok, tee to trace | B | P0 |
| 2 | Run record + harness-sensor labels per run | B | P0 |
| 3 | Scrub-on-ingest + private append-only trace store | C | P0 |
| 4 | SessionEnd hook: capture interactive Claude Code sessions | B | P1 |
| 5 | Outcome backfill: review verdicts, merge, fix-follow within 7 days | A | P1 |
| 6 | Training export: normalized tool calls, time-split, held-out freeze | A | P1 |

Drafts for every child are in `hackathon/flight-recorder/draft/` (self-improving-agents repo). They're starting points, and each still needs verification against real CLI output.
