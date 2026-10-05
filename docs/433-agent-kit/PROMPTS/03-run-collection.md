# Prompt — Phase 3 Run collection

## Codex CLI (Hermes available)

```text
Phase 3: collect real Nemotron observational rows for #433.

Scope:
- Export OPENROUTER_API_KEY in the environment (do not write it to the repo)
- Prefer Hermes runner if `hermes` is on PATH; otherwise use the no-Hermes agent loop below
- Default model nvidia/nemotron-3.5-lightning; provider pin CoreWeave
- Hard stop $47: OBS_SPEND_CAP_USD=47; also touch STOP to halt
- Append-only runs.jsonl (gitignored)

Commands (Hermes):
  python3 training/dataset/observational/scripts/or_smoke.py --chat
  python3 training/dataset/observational/scripts/ensure_pristine.py
  export OBS_TARGET_ROWS=50   # start small unless Mark asked for more
  export OBS_SPEND_CAP_USD=47
  export OBS_MODEL=nvidia/nemotron-3.5-lightning
  export OBS_PROVIDER_PIN=CoreWeave
  python3 training/dataset/observational/scripts/observational_runner.py
  # halt: touch training/dataset/observational/STOP

Success checks:
- New rows appear in runs.jsonl; validate_runs.py exits 0
- provider field populated; model slug exact
- Spend under cap

STOP if: tool calling broken; provider MIXED without recording; key missing; another Mini expansion job owns the same OBS_ROOT; cost unclear.
```

## Codex / Claude **without Hermes** (computer use)

```text
Phase 3 (no Hermes): You ARE the tool-using agent.

For each task in tasks.manifest.json (batch size agreed with Mark/John):
1. Reset fixture from fixture_templates/<task_id> → fixtures/<task_id>
2. Read fixtures/<task_id>/README.md
3. Work only inside that directory; run verify_cmd
4. Independently re-run verify_cmd yourself
5. Append ONE schema-valid JSON object to runs.jsonl (observable actions only; no invented CoT)
6. Record model=nvidia/nemotron-3.5-lightning if you routed via that model through OpenRouter; if you used Codex/Claude instead, set model to the actual model id and note in provider_metadata that this is a cross-runtime trace (ask Mark first — default baseline wants Nemotron)

Do not exceed $47 OpenRouter spend. Prefer Mark’s Hermes path for Nemotron purity.
```

## Claude computer use — differences

- Monitor spend in OpenRouter dashboard / `or_smoke.py` key endpoint between chunks of 10 runs.
- If Hermes is installed on the machine, prefer the Hermes commands above for Nemotron-identical traces.
