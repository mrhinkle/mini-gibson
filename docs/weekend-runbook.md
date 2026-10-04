# Saturday Morning → Sunday Noon Runbook

## Saturday 08:00–09:00 — Environment
- launch Brev;
- run doctor;
- pin/check artifacts;
- start vLLM;
- smoke model.

**Gate 1:** Nemotron responds through vLLM.

## 09:00–11:00 — One end-to-end task
- reference agent;
- GibsonEnv;
- real read/edit/test flow;
- evidence receipt.

**Gate 2:** one issue reaches a legitimate terminal result.

## 11:00–12:00 — Recovery
Use a deterministic task with a natural failure/recovery path.

**Gate 3:** failed test → diagnosis → bounded repair → retest works.

## 12:00–13:00 — Lunch + baseline run
Machines run the pre-registered baseline while humans eat.

## 13:00–15:00 — Evidence Gate
Prove a model cannot self-award success.

**Gate 4:** unsupported completion is rejected.

## 15:00–17:00 — Harness benchmark
Run B under frozen protocol.

**Gate 5:** A/B results exist and are interpretable.

## 17:00 decision
If core experiment is unstable, stop expansion and fix it. Historical training is optional upside.

## 17:00–19:00 — Dataset validation
Validate provenance, schema, leakage, split.

## 19:00 — LoRA start
Only if training gate passes.

## 19:00–21:00 — Demo/report polish
Do not watch training logs.

## 21:00–22:00 — Adapter smoke
If training fails and fix is not obvious, preserve Silver path.

## 22:00 — C benchmark
Only if adapter is valid. Let compute run overnight.

## Sunday 07:00 — Results
Generate report and make adapter promotion decision.

## 07:30–09:00 — Freeze experimental artifacts
Pin SHAs/revisions/hashes.

## 09:00–10:00 — Six-slide presentation
1. Mini Gibson / story.
2. Problem: code generation vs engineering.
3. Architecture.
4. Experiment.
5. Results.
6. Organizational-learning vision.

## 10:00–11:00 — Demo rehearsal
Three successful rehearsals plus backup trace.

## 11:00 — CODE FREEZE
Only presentation/rehearsal after this point.

## 12:00 — Present
