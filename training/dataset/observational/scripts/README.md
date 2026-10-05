# Observational runners (#433)

| Script | Purpose |
|--------|---------|
| `or_smoke.py` | Direct OpenRouter key/model/provider smoke (no Hermes, no tools) |
| `ensure_pristine.py` | Reset `fixtures/` from `fixture_templates/`; assert fix-tasks fail |
| `observational_runner.py` | Hermes oneshot collector → `runs.jsonl` |
| `observational_runner_parallel.py` | 3-worker wrapper |
| `validate_runs.py` | Schema + invariant check |
| `split_dataset.py` | Held-out TEST split by `task_id` |

Legacy Mini names `scale_runner.py` / `scale_runner_v2.py` are **not** shipped; they hard-coded `/Users/...` and `/tmp/or-key-433.env`. Use the portable scripts above.

## Hermes vs no-Hermes

- **With Hermes:** export `OPENROUTER_API_KEY`, optional `HERMES_HOME` / `HERMES_BIN`, then run `observational_runner.py`.
- **Without Hermes:** use `or_smoke.py` for credentials, then follow `docs/433-agent-kit/PROMPTS/` with Codex CLI or Claude computer use to execute tasks and append validated rows (full tool loop is the agent, not these scripts).
