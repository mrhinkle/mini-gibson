# Expansion design — toward ~1,000 hackathon traces

**Status:** A separate process on Mark’s Mac Mini is expanding beyond the first 300 rows. **Do not interfere** (no tmux attach, no Carmack model pin edits, no deleting that `runs.jsonl`). This document is the design agents should follow when authoring the next fixtures/verifiers in-repo.

## Why expand

The 300-row CoreWeave/Nemotron batch is real and schema-valid but weak for learning:

- ~97% pass rate → thin failure/recovery signal (#433 wanted ≥10 fail/partial and ≥5 recovery traces *naturally*).
- Investigate success is mostly **claim-based**.
- No held-out **TEST** split.
- Tasks are small synthetic practice problems (fine for DEV, insufficient alone for robust stats).

## Target shape (~1,000 rows)

| Lever | Plan |
|-------|------|
| More attempts | Up to ~5–8 attempts/task across 100–150 task_ids |
| Harder tasks | Multi-bug, “don’t edit tests”, misleading READMEs, cross-file wiring |
| Investigate verifiers | `expected.json` with `{path, field, value}`; score agent report |
| Turn pressure | Lower `OBS_MAX_TURNS` on a subset to induce repair traces |
| Split | `split_dataset.py` ~20% task_id → TEST_OBSERVATIONAL |
| Spend | Still **$47 hard cap per batch**; expect ~$5–$20 total at current $/run |

## Phase mapping

1. **Author ~100 harder tasks** (kinds: `hard`, `multifile`, `debug`, adversarial investigate).
2. **Verifiers** for investigate + keep unittest for code tasks.
3. **Run** with portable runner or Codex/Claude prompts; append-only JSONL.
4. **Validate** + quarantine claim-only if investigate keys exist.
5. **Split** and freeze TEST.
6. **Baseline report** on DEV only; peek at TEST only for final numbers Mark approves.

## Fixture conventions (new tasks)

```
fixtures/<task_id>/
  README.md          # DEV_OBSERVATIONAL; goal; verify command
  ... source/tests ...
  expected.json      # optional; required for kind=investigate in expansion
```

`tasks.manifest.json` entry:

```json
{
  "task_id": "dev-hard-example",
  "kind": "hard",
  "lang": "python",
  "path": "fixtures/dev-hard-example",
  "verify_cmd": "python3 -m unittest -q",
  "synthetic": true,
  "goal": "..."
}
```

## Anti-goals

- Do not manufacture fake failures (issue forbids injecting fake failures solely for interesting traces).
- Do not mix providers silently.
- Do not copy Mini `/tmp/or-key-433.env` into the repo.
