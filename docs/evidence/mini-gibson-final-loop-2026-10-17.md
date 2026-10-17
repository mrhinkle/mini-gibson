# Mini-Gibson experiment status report

**Evidence cutoff:** 2026-10-17 23:54 UTC  
**Repository:** `mrhinkle/mini-gibson`  
**Verified main before this report:** `3a8f751dde5e9f7ff0e3f322f61b81ae6b93d374`  
**Claim status:** v1 complete and not promotable; v2 infrastructure complete; v2 qualification, training, and evaluation blocked by Brev credits.

## Executive summary

The first Nemotron 3.5 Lightning LoRA experiment produced a meaningful directional coding gain but failed the preregistered statistical and reliability gates. It resolved 16 of 48 fresh development issues versus 9 of 48 for the frozen base model, a gain of 7 tasks or 14.58 percentage points. The paired one-sided exact p-value was 0.0717, so the evidence does not establish an upgrade. More importantly, malformed tool responses affected 21 of 48 tuned tasks versus 8 of 48 base tasks, a significant reliability regression.

The repository now contains the complete compute-independent v2 experiment infrastructure: a bounded sequential design, 456 outcome-blind frozen SWE-rebench candidates, a hardened networkless evaluator, and a crash-safe resumable qualification orchestrator. All relevant work was merged through independently reviewed pull requests. The latest complete repository test run passed 281 tests.

The experiment itself is not finished. Brev currently lists only a stopped 2xA100 instance; the previous H100 environments are absent. The last A100 start attempt failed because the account reported exhausted credits. No v2 qualification, training, pilot, formal development evaluation, or final-holdout run has occurred.

## What we learned from v1

| Measure | Base | v1 tuned | Difference |
| --- | ---: | ---: | ---: |
| Resolved issues | 9/48 | 16/48 | +7 tasks / +14.58 pp |
| Tuned-only / base-only paired wins | — | 12 / 5 | one-sided exact p=0.0717 |
| Tasks with malformed responses | 8/48 | 21/48 | tuned worse, p=0.000488 |
| Harness errors | 0 | 0 | none |
| Policy violations | 0 | 0 | none |
| Test tampering | 0 | 0 | none in the frozen v1 study |

Stage 1 showed a large +25-point gain, while the fresh second stage showed only +4.17 points. The effect did not replicate strongly enough to cross the frozen boundary. A post-study diagnostic showed that the original 512-token response cap caused many malformed outputs, but raising the cap did not remove the reliability problem. These diagnostics do not change the frozen 48-task result.

Supported conclusion: **fine-tuning can improve issue resolution, but this adapter is not yet a reliable or statistically established upgrade.**

## What is now merged

| Capability | Evidence |
| --- | --- |
| Preregistered sequential inference | PR #26, merge `d7d5eace68679c5dbd7ce82d48b1b621f2eb3308` |
| Outcome-blind 24+144+144+144 cohort freeze | PR #28, merge `91b5c4aa110e5b5131061408c9508d372220f7ca` |
| Networkless, fail-closed Docker evaluator | PR #27, merge `3ff5dfdc37835b8db658e3f2e805e02b231be473` |
| Fsynced, hash-chained resumable qualification | PR #29, merge `3a8f751dde5e9f7ff0e3f322f61b81ae6b93d374` |
| Editable demo evidence-hash fix | PR #18, merge `7ad03e97f96b5d53fa6a1cd7a892743a738beb37` |

The evaluator rejects mutable image references, host-network access, host mounts, Docker socket exposure, over-limit output during execution, unbound parsers, inconsistent receipts, protected-test mutation, ambiguous patch paths, malformed multi-file diffs, and binary patches. Candidate qualification requires exactly two base failures and two gold passes.

The qualification orchestrator verifies every frozen hash before execution, checks locally present immutable image digests without pulling, appends each completed receipt with `O_APPEND` and `fsync`, chains records by SHA-256, resumes idempotently, and refuses to emit runnable locks until all 456 candidates qualify.

## Frozen v2 experiment

- Exact source: `nebius/SWE-rebench-V2` revision `10483de0f50fe5da545942705a76c6150171af7f`.
- Source Parquet SHA-256: `0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`.
- Source size: 32,079 rows; 17,822 eligible before exclusions.
- Frozen tasks: 24 budget-pilot tasks plus three development cohorts of 144 each.
- Confirmatory maximum: 432 development tasks.
- Cross-cohort uniqueness: instance ID plus issue, product-patch, test-patch, changed-file, and image-cluster fingerprints.
- Final Gibson Bench holdout: sealed and excluded from training, prompt development, and current evaluation.

The primary v2-versus-base analysis inspects only N=144, 288, and 432. It uses exact paired McNemar tests with local alpha budgets 0.01, 0.015, and 0.025, requires at least +5 percentage points observed uplift, and applies frozen efficacy, futility, malformed-response safety, and tamper/isolation gates. The experiment stops at success, safety failure, futility, or N=432. It will not add tasks until a p-value becomes significant.

## Current infrastructure state

At the evidence cutoff, Brev returned:

| Instance | ID | Machine | State |
| --- | --- | --- | --- |
| `weird-white-ocelot` | `ds7uiptfk` | `a100-80gb.2x` | stopped; build complete; shell not ready |

No Brev Connect nodes were present. The former `mini-gibson-lightning-ft` and `mini-gibson-ocr7b-lora` H100 environments were not listed. The last A100 start attempt failed with an exhausted-credit message. We did not stop or delete the missing environments, purchase credits, or create replacement compute. Active GPU compute is $0/hour while the listed A100 remains stopped.

## Remaining work

1. Mark restores Brev credits or explicitly selects another approved compute provider within the $30/hour cap.
2. Seal the exact 456-row materials/parser/AST package and immutable image lock.
3. Dry-run and then execute repeated qualification for all 456 candidates.
4. Freeze the final training exclusion registry.
5. Construct v2 from successful executable OpenHands/Scale-SWE trajectories outside all evaluation sets, with at most 10–20% SWE-smith auxiliary data.
6. Run the one-step smoke and bounded resumable v2 fine-tune.
7. Use only the pilot to freeze the turn budget.
8. Run identical base/v1/v2 evaluation at the three formal looks and apply the frozen gates.
9. Open the 35-task final holdout only after all development gates pass.
10. Update and re-render the demo with the verified terminal findings.

## Decision for John and Mark

Do not promote v1. Do not describe v2 as trained or evaluated. The project has a credible directional hypothesis, a materially stronger dataset and evaluator, and a defensible bounded protocol. The next required action is operational rather than scientific: restore approved compute, then execute the already-frozen experiment without changing its thresholds or task set.
