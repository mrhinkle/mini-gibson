# Mini Gibson — submission summary

**Team: Merge-Geezers** · **Project: Mini Gibson**

## The short version

Mini Gibson is a **training and evaluation pipeline for coding agents**. It
turns engineering histories into training data, fine-tunes a small open model,
runs the base and tuned models under the same rules, and keeps receipts that
show exactly what passed, failed, or was stopped.

We are not submitting a finished autonomous developer. We are submitting the
repeatable system that helps us improve one without hiding bad results.
For the model, data, training, and evaluation sequence, see the
[plain-language LLM story](docs/LLM-STORY.md).

## Why we built it

Coding agents can generate more code than a person can comfortably check. The
result is a new bottleneck: humans spend too much time restating context,
checking work, rescuing failed attempts, and deciding whether an agent is truly
finished.

Our question was simple:

> Can a small model learn better software-engineering behavior from real
> engineering trajectories while an independent evidence system keeps the
> quality bar fixed?

## What we built

1. A data pipeline for historical engineering trajectories, including failed
   attempts and verified outcomes.
2. A bounded LoRA fine-tuning pipeline for NVIDIA Nemotron 3.5 Lightning.
3. A locked-down evaluator that gives every model the same tasks, tools,
   budgets, and pass criteria.
4. Tamper-evident receipts, immutable hashes, stop rules, and a sealed final
   holdout.
5. A public evidence package that preserves negative results instead of
   rewriting them as success.

The public repository also includes our sanitized synthetic-fixture
[1,000-row v1.1 observational release](training/dataset/observational/releases/433-v1.1-sanitized/)
and [105-row harder development release](training/dataset/observational/releases/433-v2-hard/).

## What the completed comparison found

On 48 development issues, the base model solved **9** and the tuned model solved
**16**. That is a promising observed increase of **14.58 percentage points**,
but it did not cross the statistical boundary we set in advance
(`p=0.0717316`). The tuned model also affected many more tasks with at least one
malformed response: **21 of 48**, compared with **8 of 48** for the base model
(`p=0.000488`).

Therefore, the adapter was **not promoted**. The honest conclusion is that the
fine-tune showed a directional quality signal while making reliability worse.
We need better tool-call training and a stronger fresh evaluation before we can
claim an improvement.

## What the successor experiment found

The successor checked all **456** frozen SWE-rebench task packages for safe
evaluator compatibility: **406 were compatible and 50 were not**. Of the 50,
47 had a changed checkout before patching and three gold patches touched a
protected test path. Under our prewritten rules, that stopped the run before
qualification, another fine-tune, or model evaluation. This screen ran no
model, agent, parser, or tests, so it does **not** measure model improvement.

The [verified terminal report and complete matrix](docs/evidence/mini-gibson-successor-2026-10-18/REPORT.md)
include hashes, cost, and limitations. The 35-task final holdout remained
operationally sealed and unconsumed. The earlier
[time-stamped progress snapshot](docs/evidence/mini-gibson-successor-2026-10-18/INTERIM-STATUS.md)
is retained as history, not as the terminal result.

## What comes next

We cannot simply drop incompatible packages to make a smaller cohort. A future
run would need a general, outcome-blind evaluator repair and a new written
protocol for the entire cohort, or a genuinely fresh cohort. Only after
compatibility and qualification pass can we train on additional successful
OpenHands or Scale-SWE trajectories, with a small SWE-smith auxiliary share.

Langfuse and Jev are proposed **post-run** analysis tools. Langfuse can help us
see repeated tool-use and recovery patterns. Jev can classify bounded
operational anomalies after local results are final. Neither tool can change a
score, authorize a retry, promote an adapter, or unseal the holdout.

We separately exercised [NeMo Gym](integrations/nemo_gym/README.md) locally:
its pinned upstream verifier example passed five tests, and our synthetic
Mini Gibson tool-call-format fixture passed one test with four cases. This is
a working integration smoke, **not** a Nemotron rollout, scored evaluation, or
claim that Gym participated in the completed model comparison.

## Hackathon track

Our primary entry is the **Tool-Calling** track. Mini Gibson focuses on valid
tool selection and arguments, error recovery, verification, safe stopping, and
reproducible evidence. It uses NVIDIA Nemotron 3.5 Lightning within the
challenge's 33-billion-parameter limit.

## Start here

- [Main repository](https://github.com/mrhinkle/mini-gibson)
- [Project, repository, model, and dataset map](docs/PROJECT-MAP.md)
- [Plain-language LLM story](docs/LLM-STORY.md)
- [NeMo Gym integration and smoke receipt](integrations/nemo_gym/README.md)
- [Editable final-findings deck](presentation/final-findings/README.md)
- [Narrated demo and editable video project](presentation/demo/README.md)
- [Completed v1 and stopped v2 evidence](docs/evidence/mini-gibson-v2-2026-10-18/REPORT.md)
- [Successor protocol and evidence](docs/evidence/mini-gibson-successor-2026-10-18/README.md)
- [Langfuse and Jev improvement plan](docs/evidence/mini-gibson-successor-2026-10-18/CONTINUOUS-IMPROVEMENT.md)

This submission reports the completed v1 comparison and the terminal successor
compatibility result. There is no new v2 model result, formal N=144/288/432
look, or final-holdout score.
