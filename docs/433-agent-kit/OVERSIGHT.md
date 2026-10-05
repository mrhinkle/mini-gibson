# OVERSIGHT — Mark & John

Human oversight checklist for the #433 observational pipeline. Agents execute; you approve gates and halt on red flags.

## Per-phase checklist

### Phase 0 — Bootstrap
- [ ] Agent read `WORKPLAN.md` + issue #433
- [ ] `OPENROUTER_API_KEY` present in **environment only** (not in repo, not committed)
- [ ] `or_smoke.py` succeeds (optionally `--chat` with provider pin)
- [ ] `ensure_pristine.py` exits 0
- [ ] `git status` clean of `.env` / `or-key*` / full `runs.jsonl`

### Phase 1 — Author tasks
- [ ] New fixtures marked DEV_OBSERVATIONAL
- [ ] No overlap with SWE-rebench / Gibson temporal / Mini final eval holdouts
- [ ] Pristine fix-tasks fail tests
- [ ] Manifest updated

### Phase 2 — Verifiers
- [ ] Investigate tasks have answer keys (not claim-only)
- [ ] Verifier scripts runnable offline without API spend

### Phase 3 — Run
- [ ] `OBS_SPEND_CAP_USD` ≤ **47** per batch (default)
- [ ] STOP file mechanism known (`training/dataset/observational/STOP`)
- [ ] Model still `nvidia/nemotron-3.5-lightning`, provider pin CoreWeave (or documented change)
- [ ] Not racing the Mini’s in-flight expansion job
- [ ] Sample of 3 stream logs reviewed (tool calls look real)

### Phase 4 — Validate
- [ ] `validate_runs.py` exit 0
- [ ] Claim-based investigate rate reviewed (should fall after Phase 2)
- [ ] Cost sum plausible vs OpenRouter dashboard

### Phase 5 — Split
- [ ] TEST task list frozen and recorded in `split_meta.json`
- [ ] No prompt iteration against TEST tasks

### Phase 6 — Report
- [ ] Twelve #433 analysis bullets present
- [ ] Five hackathon hypotheses stated as Observation → Hypothesis
- [ ] Paths to full JSONL (Mini) cited; no keys in report

## Spend caps

| Control | Default | How |
|---------|---------|-----|
| Hard batch cap | **$47** USD | `OBS_SPEND_CAP_USD` + runner STOP when ≥98% of cap |
| Manual halt | immediate | `touch training/dataset/observational/STOP` |
| Soft expectation | ~$0.005–0.02 / run | 300 rows ≈ $1–$6; 1000 rows ≈ $5–$20 if similar |

Record OpenRouter `limit_remaining` before/after a batch if not using Hermes DB costs.

## What to review before approving a batch

1. **Provider column** — all CoreWeave (or explained MIXED).
2. **Verifier mix** — prefer `independent_verify_pass/fail` over `claim_based_investigate`.
3. **Failure labels** — non-empty on failed/partial rows.
4. **Wandering** — `files_inspected` stay inside fixture paths.
5. **Config drift** — model slug + system_instructions stable within a batch.
6. **Secrets** — `rg`/`gitleaks` clean; no `/tmp/or-key` copies in commits.

## Red flags → halt

| Flag | Action |
|------|--------|
| Claim-only “VERIFIED” with failing tests | STOP; fix classify/verify before more spend |
| Config drift mid-batch (model/provider/prompt) | STOP; split batches in report |
| API key in file under repo or world-readable `/tmp` | STOP; rotate if exposed; delete file |
| Agent edits `AGENTS.md` / billing / schema migrations without ask | STOP; revert |
| Holdout task contamination suspected | STOP; quarantine rows |
| Spend probe fails open while continuing blindly | Prefer fail-closed once past smoke |

## How to halt

```bash
# from repo root (or set OBS_ROOT)
touch training/dataset/observational/STOP

# if Hermes parallel runner on Mini — same STOP path under that OBS_ROOT
# do not kill unrelated Carmack velocity jobs unless necessary
```

To resume: remove STOP only after oversight review; reset spend baseline env if starting a new $47 batch.

## Roles

- **Mark / John:** approve spend, merge PRs, freeze TEST split, accept baseline report.
- **Agent (Codex / Claude / Carmack):** execute phases; never merge gate-removal or kit PRs unless explicitly told; never commit secrets.
