# #433 Agent handoff kit (Mini Gibson observational baseline)

**Start here** if you are Codex, Claude (computer use), or another coding agent pointed at this repo by Mark or John.

Canonical issue: https://github.com/The-AIE/the-gibson/issues/433  
Parent kickoff: [`docs/433-nemotron-baseline-kickoff.md`](../433-nemotron-baseline-kickoff.md)

## Exact first prompt

Copy-paste this as your first message (Codex CLI or Claude computer use):

```text
Read docs/433-agent-kit/README.md and docs/433-agent-kit/WORKPLAN.md.
You are collecting DEV_OBSERVATIONAL Nemotron traces for The-AIE/the-gibson#433.
Do not invent traces. Do not touch holdouts. Do not fine-tune Mini Gibson.
Follow docs/433-agent-kit/PROMPTS/00-bootstrap.md next.
Hard stop: $47 OpenRouter per batch via STOP file or OBS_SPEND_CAP_USD.
Report status to Mark/John using docs/433-agent-kit/OVERSIGHT.md checklist.
```

## Kit map

| Path | What |
|------|------|
| [`WORKPLAN.md`](WORKPLAN.md) | Phases, acceptance, current status (~300 rows done; expansion to ~1k in progress on Mini) |
| [`OVERSIGHT.md`](OVERSIGHT.md) | Mark & John checklist, spend caps, red flags, how to halt |
| [`EXPANSION.md`](EXPANSION.md) | Design for ~1000 rows: harder tasks, investigate verifiers, DEV/TEST split |
| [`PROMPTS/`](PROMPTS/) | One copy-paste prompt per phase (Codex + Claude notes) |
| [`../../training/dataset/observational/`](../../training/dataset/observational/) | Schema, fixtures, portable runners, sample JSONL |

## Non-goals

- Do not implement Mini Gibson harness / LoRA / Brev GPU work here (#415/#416).
- Do not merge PRs unless Mark/John explicitly ask.
- Do not commit `OPENROUTER_API_KEY`, `/tmp/or-key*.env`, or full `runs.jsonl` (gitignored; sample only in-repo).
