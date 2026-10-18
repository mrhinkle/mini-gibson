# Mini-Gibson final findings

**Evidence state:** terminal compatibility preflight, frozen at `2026-10-18T15:26:34Z`

**What we are submitting:** a reproducible training and evaluation pipeline for improving coding agents. This is not a production-ready autonomous coding model release.

## The plain-language result

We built a pipeline that turns real engineering histories into bounded LoRA training data, runs model variants through the same locked evaluator, and records the result in tamper-evident receipts.

The first fine-tune produced a useful signal: the tuned model resolved **16 of 48** development issues, compared with **9 of 48** for the base model. That is a **14.58 percentage-point increase**. However, the result did not cross the preset statistical threshold (`p=0.0717316`), and tasks affected by malformed responses rose from **8 of 48** to **21 of 48** (`p=0.000488`). We therefore did not promote the adapter.

The successor experiment checked whether all 456 frozen task packages could run safely in the networkless evaluator before any more training or model testing. It found **406 compatible** packages and **50 incompatible** packages. Because the full cohort was not compatible, the registered protocol stopped before qualification, training, or model evaluation.

## What this proves

- The complete training and evaluation workflow is real, reproducible, and capable of stopping itself when the evidence is not good enough.
- Fine-tuning may improve issue resolution on development tasks.
- Reliability must improve with task resolution. More malformed tool calls make an adapter unsafe to promote.
- Compatibility preflight belongs before expensive training and evaluation. It found cohort problems without running a model or consuming the final holdout.

## What this does not prove

- It does not establish that the fine-tuned model is better than the base model.
- It does not establish production readiness or reduced human intervention.
- The successor preflight provides no new model-quality evidence. It ran no model, agent, parser, or tests.
- The public 35-task Gibson Bench final holdout remains operationally sealed and unconsumed by the pipeline.

## Successor compatibility matrix

| Boundary | Verified result |
| --- | ---: |
| Frozen candidates | 456 |
| Compatibility receipts | 456 |
| Compatible | 406 |
| Incompatible | 50 |
| Model or agent runs | 0 |
| Test executions | 0 |
| Formal development sample | N=0 |
| Final holdout | operationally sealed and unconsumed |

Incompatibility classes: `dirty_image_checkout_before_patching`: 47, `gold_patch_touches_protected_test_path`: 3.

The preregistered rule forbids a 455-plus-one cohort or selective retries. A future run needs one generic, outcome-blind evaluator repair and a complete new 456-task preflight under a new experiment identity.

## Why the pipeline is the project

The durable contribution is the system for continuous improvement:

1. prepare and exclude contaminated trajectory data;
2. run a bounded LoRA fine-tune with resumable checkpoints;
3. compare base and tuned models with identical tasks and budgets;
4. enforce network, patch, test, and completion boundaries outside the model;
5. keep failed, malformed, and incompatible attempts in the evidence;
6. stop at registered statistical, safety, futility, or infrastructure boundaries.

The next addition is post-run observability. Langfuse can show safe, redacted timing and tool-use patterns after a run ends. Jev can classify bounded operational anomalies. Neither service may change a task result, authorize a retry, or replace the local evaluator.

## Reproduce the evidence check

```bash
python3 docs/evidence/mini-gibson-successor-2026-10-18/verify_evidence.py
```

The verifier checks every SHA-256 journal link, all 456 R3/v2 preflight receipts, their frozen-cohort bindings, the terminal manifest, the public matrix and summary, the operational holdout boundary, cost arithmetic, and the complete package hash list.

## Cost

The R3 controller ran for an estimated 4.3128 hours on two A100 80 GB GPUs at `$3.96/hour`, for approximately **$17.0794** during the controller window. This stayed below the approved `$30.00/hour` cap. The Brev instance remains running; later charges are outside this evidence window.
