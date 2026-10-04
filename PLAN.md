# Mini Gibson — Complete Hackathon Plan

## Mission

By Sunday noon, present a reproducible experiment answering:

> Can a small open model become measurably more reliable at autonomous software engineering when it operates inside an evidence-driven engineering environment, and improve further by learning from real historical engineering trajectories?

## Deliverables

1. Mini Gibson LoRA adapter, if held-out evidence justifies promotion.
2. Frozen Experiment Manifest v0.1.
3. GibsonEnv v0.1.
4. Agent Adapter Conformance v0.1.
5. Gibson Bench v0.1.
6. Curated Gibson historical trajectory dataset.
7. Dataset validation/conversion pipeline.
8. Nemotron LoRA training/export pipeline.
9. Reproducible vLLM inference environment.
10. Experiment runner + immutable telemetry/results.
11. Brev Launchable.
12. Judge-ready live demo.
13. Benchmark report.
14. Technical report / model card / benchmark card.

## Success tiers

### Bronze
Base Nemotron completes one task through GibsonEnv with evidence-based VERIFIED.

### Silver
Controlled baseline vs Gibson Harness comparison produces defensible measured results.

### Gold
Historical Mini Gibson adapter is trained and produces held-out improvement over base Nemotron + Gibson under the frozen protocol.

A failed LoRA promotion does not invalidate Silver.

## Critical path

1. Complete #417 design review.
2. Freeze hypotheses/protocol/conformance/manifest.
3. Finish environment and runner.
4. Freeze Gibson Bench before tuning.
5. Curate/validate historical dataset.
6. Capture baseline and harness measurements.
7. Train LoRA.
8. Evaluate on untouched holdouts.
9. Promote or reject adapter.
10. Rehearse Brev Launchable and demo.
11. Freeze Sunday presentation artifacts.

## Hard rules

- Agent/model cannot award VERIFIED.
- No hidden frontier-model assistance inside controlled Nemotron runs.
- Infrastructure retries are not task retries.
- No holdout is used to tune prompts, harness, reward, or LoRA.
- All reported trials count.
- Negative results are reported.
- Reproducibility-critical revisions are pinned.
- No new feature after Sunday 9:00; code freeze Sunday 11:00.

See docs/ for protocol, build, demo, and operations plans.
