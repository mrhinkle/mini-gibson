# Nemotron baseline collection kickoff (#433)

**Status:** Agent handoff kit lives in `docs/433-agent-kit/`. First Mini batch produced **300** real rows (full JSONL stays on the Mini; sample in-repo). Collection remains observation-only via OpenRouter — **do not invent traces**.

Canonical issue: https://github.com/The-AIE/the-gibson/issues/433  
Env scaffold (draft): https://github.com/The-AIE/the-gibson/pull/416  
Env issue: https://github.com/The-AIE/the-gibson/issues/415

## What exists vs missing

| Item | Status |
|------|--------|
| Issue #433 contract | Done |
| Neuro OpenRouter credential | Provisioned (do not log key) |
| Carmack `OPENROUTER_API_KEY` | Confirm injection / Neuro gateway route |
| Historical schema on Gibson #416 | Exists; **wrong shape for #433 observational runs** |
| OpenRouter collector / JSONL | **Missing** |
| Brev GPU | **Not required** for #433 (needed for #415 / LoRA later) |

## Secrets / approvals (Mark)

1. Approve OpenRouter spend on paid `nvidia/nemotron-3.5-lightning` this week.
2. Ensure Carmack (or Neuro gateway) can call OpenRouter with tools.
3. Assign Carmack to #433 / `working_on`.
4. Brev + HF tokens only when starting #415 env — not blockers for baseline collection.

## Output layout

```
training/dataset/observational/
  schema.observational.v0.1.json
  tasks.manifest.json
  runs.jsonl              # one JSON object per completed run — real data only
  README.md
```

Historical LoRA schema (Gibson #416) stays separate; convert later if needed.

## Carmack runbook (start today)

### 0. Credential smoke
```bash
test -n "$OPENROUTER_API_KEY" || { echo "OPENROUTER_API_KEY missing"; exit 2; }
curl -sS https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  | jq -r '.data[].id' | rg -i 'nemotron'
```

### 1. Provider pin
1. Run 2–3 tool-capable smokes across available providers.
2. Pick **one** stable tool-capable provider for the week.
3. Pin it on every request; record `provider` on every JSONL row.
4. If pin fails, still record actual provider per request and flag variation in the report.

### 2. Stable config (do not change mid-collection)
- Model: `nvidia/nemotron-3.5-lightning` (paid route)
- Same system prompt, tool set, agent/runtime version
- DEV / OBSERVATIONAL tasks only — never SWE-rebench holdout, Gibson temporal holdout, or Mini Gibson final eval

### 3. Task mix (30+)
- 8–10 straightforward repo fixes
- 6–8 investigation/navigation
- 6–8 failing-test/debug
- 5–8 tool-selection-heavy
- Prefer natural failure → diagnosis → repair (≥10 fail/partial, ≥5 recovery traces when natural)

### 4. Per-run fields
See `schema.observational.v0.1.json`. Capture observable actions only — no invented CoT.

### 5. Acceptance
- ≥30 validated JSONL rows (or documented constraint)
- Provider + model provenance on every row
- Failure taxonomy labels applied
- Baseline report (12 bullets from #433) written beside the JSONL
- No Mini Gibson fine-tune in this issue

## Immediate next action
**Carmack:** smoke → pin provider → first 3 DEV tasks → append real rows to `runs.jsonl`.  
**Mark:** credit/key confirmation + assign Carmack.
