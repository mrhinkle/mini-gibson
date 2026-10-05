# Observational baseline dataset (#433)

Schema: [`schema.observational.v0.1.json`](schema.observational.v0.1.json)  
Manifest: [`tasks.manifest.json`](tasks.manifest.json) (60 synthetic DEV tasks)  
Sample rows: [`runs.sample.jsonl`](runs.sample.jsonl) (10 real traces; paths scrubbed)  
Runners: [`scripts/`](scripts/)

Full `runs.jsonl` is **gitignored** (lives on Mark’s Mini under `~/hermes-workspace/mini-gibson-obs-433/...`). First completed batch: **300** rows, CoreWeave-pinned Nemotron, ~$1.60. Expansion toward ~1k is documented in [`docs/433-agent-kit/EXPANSION.md`](../../../docs/433-agent-kit/EXPANSION.md).

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
