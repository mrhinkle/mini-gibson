> **Archived snapshot from 2026-10-15; superseded, not an operational runbook.**
> Preserved during readiness consolidation on 2026-10-16. The text below records
> discovery and candidate proposals at that date, including stale PR state,
> pre-export measurements, superseded filenames and unapproved settings.
> PR #14 has since merged, and the exporter and CPU adapter now exist.
> Use the [current readiness index](../../README.md),
> [data preparation guide](../../../readiness-data-preparation.md), and
> [trainer interface guide](../../../readiness-trainer-interface.md).
> The current exporter's complete-batch response-order normalization supersedes
> the earlier strict-order proposal. Candidate parameters are not frozen by this
> archive. Hardware, GPU spend, release eligibility and protocol decisions remain
> unresolved; archived commands must not be used as launch instructions.

# Experiment candidate: minimal A/B/C with go/no-go ledger

Status: CANDIDATE v2, 2026-10-15, revised on coordinator review. Nothing is frozen. #417 (Kimi K3 / GLM-5.2 / Claude design synthesis) is open; no Kimi or GLM output exists in this repository; `experiment.example.yaml` says `Freeze only after Kimi K3 / GLM-5.2 / Claude design review`. This document is the Claude input to that synthesis. It does not change `docs/experiment-protocol.md`, `experiment.example.yaml`, or any review gate.

## 1. Arms

| Arm | Served model | Environment | Differs from A only by |
| --- | --- | --- | --- |
| A fair baseline | base Nemotron, pinned revision, vLLM name `nemotron-base` | same tool contract, statement, budgets, and repair opportunity as B; completion self-declared | nothing |
| B Gibson | same endpoint | GibsonEnv: evidence receipt, completion authority `gibson`, repair enforcement | enforcement mechanisms, not budget |
| C historical Mini Gibson | `mini-gibson`: LoRA merged into a full HF checkpoint before vLLM, per the official custom-data path found in Grok's audit | identical to B | merged weights |

Direct PEFT adapter export and vLLM adapter loading are unverified; the merged checkpoint is the documented candidate. H1 is A vs B, H2 is B vs C. C runs only if a training run exists and passes `docs/training-plan.md` promotion. Silver is A vs B alone.

## 2. Controls to freeze (candidate values, all open until #417 closes)

| Control | Candidate |
| --- | --- |
| Tasks | Gibson Bench v0.1, 35 tasks, `FROZEN_v0.1`, `frozen_on 2026-10-13T15:30:05Z`, per-task sha256 in `bench/manifest.v0.1.json`; manifest file sha256 recorded at freeze. `development` and `validation` are empty: no tuning on any of the 35 |
| Statement | `problem_statement` + `issue_title` verbatim, identical across arms; `bench/check_statements.py` exit 0 at freeze |
| Model revision | one HF SHA chosen on Brev after the vLLM smoke; the tokenizer analysis pin `a9904d24` is not it until recorded as such |
| Inference policy | temperature 0, top_p 1, fixed seed, identical `max_tokens`; recorded, not claimed deterministic under MoE batching |
| Tool contract | one frozen contract, identical for A, B, C; does not yet exist; derived data keys must not define it |
| Budgets per trial | identical for every arm: tool calls, total tokens, context per request, wall clock, and repair opportunity. Candidate 40 calls, 400,000 tokens, 65,536 context, 20 minutes, 3 repairs. Gibson enforces inside the same budget |
| Trials | minimal candidate 1 trial × 35 tasks × 3 arms = 105 trials. 3 trials at 20 minutes is 105 GPU-hours worst case and is not assumed to fit. Repetitions are contingent on DEV pilot throughput and approved compute, and are frozen before any held-out run |
| DEV rehearsal | a separate synthetic DEV set, not drawn from the 35, for pilots and throughput measurement |
| Verifier | `bench/verify.py` as frozen, same binary and settings for A, B, C, run inside a container or VM, by a process that did not produce the patch |
| Jev and other models | `enabled: false`; no reviewer or judge model inside the scoring loop |
| Agent | one immutable reference agent for all arms; vendor runtimes are `UNFROZEN` in `docs/agent-conformance.md` and are ecological-only until a conformance test passes |

Arms interleave task by task under a seeded, recorded order so drift lands equally.

## 3. Scoring rules

- Primary: verified task resolution rate = resolved trials / all trials per arm, same independent deterministic verifier for every arm. Secondary metrics from `docs/experiment-protocol.md`, labels from `bench/failure-taxonomy.json`.
- Scored failures: invalid or empty patch, patch that does not apply, model or agent timeout inside its budget, budget exhaustion, verifier `resolved: false`. None of these triggers a retry.
- Infrastructure retry only for an evidenced external fault (endpoint down with a health-check receipt, mirror or `node_modules` missing, container failure) under the frozen written rule, once. Both attempts keep their receipts; tables report resolved / all trials with the excluded count beside the denominator.
- Test tampering: `verify.py` reverts `test_globs` edits; scoring also diffs each patch against the globs and hand-reviews edits to imported helpers (`bench/README.md` known limits).
- Independent verification: runner code is reviewed once by a different vendor before scored runs. After runs, verifier receipts (patch sha256, task hash, verifier output) are mechanically re-run by a different vendor; no model is re-called per trial. A non-reproducing verdict flips to the reproduced value and is logged.
- Uncertainty: Wilson 95% interval on the trial-level rate; paired per-task differences with a bootstrap over 35 tasks; report plainly that 35 trials per arm cannot show small effects. No p-values.

## 4. Dry run versus rehearsal

No-spend CPU dry run: `bench/check_statements.py` and `bench/check_contamination.py` (coordinator executed these metadata checks this turn: PASS), `verify.py` with `gold.patch` as candidate on all 35 tasks twice (needs mirrors and `node_modules`; not rerun this turn), `experiment/manifest.py` validation, reference agent against a scripted stub model replaying a recorded tool sequence, data export inspection and render passes, and a synthetic no-weights CPU container smoke that imports the Megatron container and torch loader against a tiny export. The smoke proves import and format only; actual loader runtime stays NOT_RUN. None of it is a result and none of it is a training or data GO.

GPU rehearsal (Brev): Mark's decision 2026-10-15 is GPU commands only, WAIT TO LAUNCH. Commands are prepared and reviewed, nothing is launched. When launched: vLLM smoke per `inference/README.md`, tool-call parse of the `<tool_call><function=…>` XML format, two synthetic DEV tasks × one trial on A and B, Megatron custom-data loader on a small export, LoRA smoke, merge to HF, serve `mini-gibson`. Every rehearsal receipt is retained, hashed, tagged `NOT_SCORED`, and excluded from result denominators. Nothing is deleted.

## 5. Track and release boundary

Event: https://luma.com/nvidia-redhat-small-models-hack. The listing states open datasets and that the Fine-Tuned track publishes the model openly. Mark's decision 2026-10-15: the corpus stays private. Candidate: primary submission on the Tool-Calling track with base Nemotron plus Gibson (A vs B). Whether that track requires any dataset or model publication, and whether a private-corpus entry is eligible on either track, is unconfirmed: the coordinator has prepared an organizer question and it has NOT been sent. No eligibility is assumed. Fine-Tuned track for C is contingent on organizer confirmation of what must be published and on a separate Mark decision about a merged model derived from private sessions; none exists. Silver fallback is A vs B with H2 reported as negative or not run. No release of any artifact is approved here.

## 6. Go/no-go ledger

| Gate | Evidence today | Status |
| --- | --- | --- |
| #417 synthesis (Kimi, GLM, Claude) | this document is the Claude input; no Kimi or GLM output exists | OPEN, Mark |
| Hypotheses, budgets, trials, retry rule frozen | candidates in §2 | OPEN, #417 |
| Benchmark frozen and hashed | `FROZEN_v0.1`, 35 tasks, per-task sha256 | MET; manifest file sha256 to record at freeze |
| Statement and contamination metadata checks | coordinator executed `check_statements.py` and `check_contamination.py` this turn: PASS; re-run at protocol freeze | MET for now |
| Gold patches resolve 35/35 twice locally | not rerun this turn | OPEN, pipeline lane |
| Frozen tool contract and runtime tool conformance | none; data keys are diagnostics only | NO_GO |
| Inference model revision | none | OPEN, Mark on Brev |
| vLLM serves base and parses tool calls | no live run | OPEN, pipeline lane |
| Reference agent exists and passes conformance | DRAFT conformance, no agent in repo | OPEN, pipeline lane |
| Data export `RENDER_PASS` incl. native/instrumented mask equality on every row | coordinator measured 254 renderable windows and a 5-case probe; production not built | OPEN, data lane (Grok) |
| Megatron container and torch loader import | synthetic no-weights CPU container smoke allowed; not run | OPEN, pipeline lane |
| Megatron custom-data loader actual runtime on the export | NOT_RUN | NO_GO |
| Merge LoRA to HF and serve `mini-gibson` | unverified | NO_GO |
| A baseline captured before any LoRA (`training-plan.md`) | no A run | OPEN |
| GPU launch | Mark 2026-10-15: GPU commands only, WAIT TO LAUNCH | HELD |
| Corpus release | Mark 2026-10-15: corpus stays private | DECIDED |
| Track eligibility and publication requirements | organizer question prepared by coordinator, NOT SENT | OPEN, pending organizer confirmation |
| Independent verifier and runner reviewer assigned | cross-vendor rule stated | OPEN, coordinator |

Live evidence that does not exist yet: a vLLM health response, a parsed tool call from the served model, one GibsonEnv tool action, one `verify.py` run on a real candidate patch, one Megatron loader run, one merged checkpoint. Until each exists its row stays OPEN or NO_GO regardless of worker reports.
