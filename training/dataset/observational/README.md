# Observational baseline dataset (#433)

**Empty by design until real Nemotron OpenRouter runs exist.**

- Schema: `schema.observational.v0.1.json`
- Runs file (create when first real run completes): `runs.jsonl` — one JSON object per line
- Do **not** commit invented / synthetic rows
- Split: every row `DEV_OBSERVATIONAL`
- Model: `nvidia/nemotron-3.5-lightning` via OpenRouter with provider recorded per run

Canonical process: `docs/433-nemotron-baseline-kickoff.md` and https://github.com/The-AIE/the-gibson/issues/433
