# Prompt — Phase 0 Bootstrap

## Codex CLI (copy-paste)

```text
You are bootstrapping Mini Gibson #433 observational collection in this repo.

Scope:
- Read docs/433-agent-kit/README.md, WORKPLAN.md, OVERSIGHT.md, EXPANSION.md
- Read training/dataset/observational/schema.observational.v0.1.json and scripts/README.md
- Do NOT call OpenRouter except via scripts/or_smoke.py
- Do NOT invent runs.jsonl rows
- Do NOT modify Mark’s Mac Mini Hermes profiles or attach to any running expansion job

Files to touch: none required (read-only). You may create a local notes file under /tmp only if needed (not committed).

Commands:
  test -n "$OPENROUTER_API_KEY" || echo "MISSING KEY"
  python3 training/dataset/observational/scripts/or_smoke.py
  python3 training/dataset/observational/scripts/ensure_pristine.py
  python3 training/dataset/observational/scripts/validate_runs.py --runs training/dataset/observational/runs.sample.jsonl

Success checks:
- or_smoke prints OK and lists a Nemotron model id
- ensure_pristine exits 0
- validate_runs on sample exits 0
- git status shows no secret files

STOP if: key missing; smoke fails; pristine fixtures already pass; you are asked to merge or change production models.
Then stop and report to Mark/John using OVERSIGHT.md Phase 0 checklist.
```

## Claude computer use — differences

- Prefer opening files in the IDE/browser rather than dumping huge trees into chat.
- Run the same three commands in the integrated terminal.
- If `OPENROUTER_API_KEY` is unset, **ask Mark/John** — do not scrape key files from disk.
