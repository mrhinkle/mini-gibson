# WORKPLAN — #433 Nemotron observational dataset

## Goal

Collect **real** software-engineering behavior traces from `nvidia/nemotron-3.5-lightning` (OpenRouter, provider pinned to **CoreWeave**) on synthetic **DEV_OBSERVATIONAL** fixtures, so the Mini Gibson hackathon has an empirical baseline (and later a larger few-hundred / ~1k-row dataset).

Issue contract: https://github.com/The-AIE/the-gibson/issues/433

## Current status (as of 2026-10-05 ET)

| Item | Status |
|------|--------|
| Schema `schema.observational.v0.1.json` | Done (in repo) |
| Portable runners + 60 fixtures | Done (this kit) |
| First batch | **300** validated rows on Mark’s Mac Mini (`~/hermes-workspace/mini-gibson-obs-433/.../runs.jsonl`) — **not** committed (gitignored) |
| Outcomes (batch of 300) | ~292 verified / 8 failed; CoreWeave on all rows; ~$1.60 |
| Gaps | High pass rate; claim-only investigate verifies; no held-out TEST split yet; synthetic-only tasks |
| Expansion to ~1,000 | **In progress on Mini by a separate process** — do not attach tmux, edit Carmack config, or race that runner. Copy scripts/fixtures from this kit; document design in `EXPANSION.md`. |
| Baseline report (12 bullets from #433) | Pending after expansion / sufficient failure signal |

## Phases

### Phase 0 — Bootstrap
**Do:** Read kit + issue; confirm `OPENROUTER_API_KEY`; run `or_smoke.py`; run `ensure_pristine.py`.  
**Accept:** Smoke lists Nemotron; pristine fix-fixtures fail unit tests; no secrets in git status.

### Phase 1 — Author tasks
**Do:** Add/extend fixtures under `training/dataset/observational/fixtures/` + templates; update `tasks.manifest.json`. Prefer harder / misleading tasks for failure signal (see `EXPANSION.md`).  
**Accept:** Manifest tasks ≥ current; every non-investigate fixture fails its `verify_cmd` when pristine; README in each fixture states DEV_OBSERVATIONAL.

### Phase 2 — Build verifiers
**Do:** Keep unittest/node/shell verify commands for fix/debug/refactor; add **investigate answer keys** (file + expected value) and a verifier that scores reports without trusting `VERIFIED` alone.  
**Accept:** `validate_runs.py` green on sample; investigate tasks no longer 100% claim-based in new rows.

### Phase 3 — Run collection
**Do:** Hermes path: `observational_runner.py` or parallel variant with `OBS_TARGET_ROWS`, `OBS_SPEND_CAP_USD=47`, STOP file. Or Codex/Claude prompts executing one fixture at a time and appending schema-valid JSONL.  
**Accept:** New rows append-only; provider recorded; spend under cap; Carmack velocity windows respected if sharing the Mini.

### Phase 4 — Validate
**Do:** `python3 training/dataset/observational/scripts/validate_runs.py --runs ...`  
**Accept:** Exit 0; summarize terminal/verifier/failure_labels/cost; flag claim-only rate.

### Phase 5 — Split
**Do:** `split_dataset.py` → `splits/runs.dev.jsonl` + `runs.test.jsonl` by **task_id** holdout (~20%).  
**Accept:** `split_meta.json` lists disjoint task sets; TEST tasks never used for prompt tuning in-hackathon.

### Phase 6 — Baseline report
**Do:** Write `training/dataset/observational/baseline-report.md` covering the 12 analysis bullets in #433 + five Mini Gibson hypotheses.  
**Accept:** Mark/John sign off via `OVERSIGHT.md`; Neuro/Carmack status can cite path + counts.

## What “done” means for the hackathon dataset

Minimum bar (issue #433): ≥30 real rows, provenance, failure taxonomy, baseline report, no holdout contamination.

**Hackathon-useful bar (this kit):**

1. **~300–1000** real JSONL rows (same schema), mostly independently verified.
2. **Meaningful failure signal** (not 97% pass): harder fixtures, tighter turn limits, and/or investigate keys.
3. **DEV / TEST split** by task_id with TEST frozen.
4. **Baseline report** with five Gibson hypotheses.
5. Full raw `runs.jsonl` lives on the Mini (or private storage); repo keeps schema, fixtures, runners, **sample** only.

## STOP / escalation

Stop and ask Mark/John if: tool calling broken on OpenRouter; provider pin drifts; cost controls unclear; task might be a holdout; work would implement Mini Gibson early; another hidden model enters the coding loop.
