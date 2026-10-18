# Observational baseline dataset (#433)

Schema: [`schema.observational.v0.1.json`](schema.observational.v0.1.json)  
Manifest: [`tasks.manifest.json`](tasks.manifest.json) (95 currently shipped reusable synthetic fixtures)
Sample rows: [`runs.sample.jsonl`](runs.sample.jsonl) (10 real traces; paths scrubbed)  
Runners: [`scripts/`](scripts/)

Public release documentation: [`DATASET-CARD.md`](DATASET-CARD.md)

The unversioned working `runs.jsonl` path is **gitignored**. Sanitized,
versioned public releases are committed under [`releases/`](releases/):

- [`433-v1.1-sanitized`](releases/433-v1.1-sanitized/) — recommended public
  copy of the 1,000 observational records with local home prefixes normalized;
- [`433-v1`](releases/433-v1/) — immutable original 1,000-record release,
  retained for hash continuity and not recommended for redistribution because
  it includes user-specific local home path prefixes;
- [`433-v2-hard`](releases/433-v2-hard/) — 105 harder development-only records.

The original collection expansion is documented in
[`docs/433-agent-kit/EXPANSION.md`](../../../docs/433-agent-kit/EXPANSION.md).

## Quick start

```bash
export OPENROUTER_API_KEY=...   # never commit
python3 training/dataset/observational/scripts/or_smoke.py
python3 training/dataset/observational/scripts/ensure_pristine.py
python3 training/dataset/observational/scripts/validate_runs.py \
  --runs training/dataset/observational/runs.sample.jsonl
```

Hermes collection:

```bash
export OBS_TARGET_ROWS=30 OBS_SPEND_CAP_USD=47
python3 training/dataset/observational/scripts/observational_runner.py
# halt early:
touch training/dataset/observational/STOP
```

Without Hermes: use `docs/433-agent-kit/PROMPTS/03-run-collection.md` (Codex/Claude computer use). `or_smoke.py` is the only direct-OpenRouter helper shipped (no full tool loop).
