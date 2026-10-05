# Prompt — Phase 4 Validate

## Codex CLI

```text
Phase 4: validate observational JSONL for #433.

Scope:
- Run validate_runs.py on the full runs.jsonl path Mark/John provide (local Mini path or OBS_ROOT)
- Summarize terminal_outcome, verifier_outcome, failure_labels, cost_sum, claim_based rate
- Do not delete or rewrite rows; quarantine by copying suspects to runs.quarantine.jsonl if needed

Commands:
  python3 training/dataset/observational/scripts/validate_runs.py --runs "$OBS_ROOT/runs.jsonl"

Success checks:
- Exit code 0
- Summary printed for oversight
- Red flags called out per OVERSIGHT.md

STOP if: schema errors >0; secrets detected in JSONL; provider drift unexplained.
```

## Claude computer use — differences

- Same commands; paste the summary table into the oversight chat for Mark/John.
