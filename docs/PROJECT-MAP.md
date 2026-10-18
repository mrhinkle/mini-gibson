# Mini Gibson project map

Verified October 18, 2026. This map separates the software and data that
actually participated in an experiment from references and proposed next
steps. It does not list every repository represented by the 456 SWE-rebench
tasks; the frozen task manifest is the authority for that provenance.

## Core project ecosystem

| Status | Project | Role |
| --- | --- | --- |
| Current deliverable | [Mini Gibson](https://github.com/mrhinkle/mini-gibson) | This hackathon repository: the training, evaluation, safety, and evidence pipeline. |
| Upstream engineering system | [The Gibson](https://github.com/The-AIE/the-gibson) | Evidence-driven software-development workflow. Mini Gibson originated in [The Gibson issue #433](https://github.com/The-AIE/the-gibson/issues/433). |
| Related subproject | [Agent Kontrol](https://github.com/mrhinkle/agent-kontrol) | Fleet visibility and control plane shown in the demo. It did not produce the scored Mini Gibson evidence; future trace integration remains proposed. |

## Used in the completed v1 experiment

| Component | Exact source | Use |
| --- | --- | --- |
| NVIDIA Nemotron 3.5 Lightning 30B-A3B | [model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16), revision `a9904d24bcc1d289a1950fa9d2b978c47cf903b9` | Base model and LoRA target. |
| SWE-Hero OpenHands trajectories | [dataset](https://huggingface.co/datasets/nvidia/SWE-Hero-openhands-trajectories), revision `150bc119e52c647216fce285fd801f16b6fd745b` | Directly downloaded training source. |
| NeMo AutoModel | [NVIDIA-NeMo/Automodel](https://github.com/NVIDIA-NeMo/Automodel) | LoRA training framework used by the committed configuration. |
| OpenHands | [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | Reference ecosystem for the source trajectories. This repository was not the Mini Gibson evaluator runtime. |

The SWE-Hero records retain upstream lineage to
[R2E-Gym-Subset](https://huggingface.co/datasets/R2E-Gym/R2E-Gym-Subset),
[SWE-Gym](https://huggingface.co/datasets/SWE-Gym/SWE-Gym), and
[SWE-Gym-Raw](https://huggingface.co/datasets/SWE-Gym/SWE-Gym-Raw). Those are
upstream provenance inside SWE-Hero, not direct Mini Gibson downloads.

## Public Mini Gibson datasets

The repository is public and includes these versioned, sanitized observational
releases collected by the project:

| Release | Public contents | Boundary |
| --- | --- | --- |
| [433-v1.1-sanitized](../training/dataset/observational/releases/433-v1.1-sanitized/) | 1,000 synthetic-fixture observational run records, provenance, outcomes, documented hash, and normalized user-home prefixes | Includes 827 development rows and 173 observational test rows. The test rows are public evidence but remain excluded from training. This is the recommended redistribution artifact. |
| [433-v1 original](../training/dataset/observational/releases/433-v1/) | Immutable original bytes retained at their published hash | Contains user-specific local home path prefixes. Retained for reproducibility; use v1.1 for redistribution. |
| [433-v2-hard](../training/dataset/observational/releases/433-v2-hard/) | 105 harder development-only run records across 35 tasks, with provenance, outcomes, and documented hash | Development evidence only; it is not the sealed Gibson Bench final holdout. |
| [Observational fixtures and schema](../training/dataset/observational/) | Reusable synthetic task fixtures, templates, manifests, collection scripts, and schema | Public project material, not a mirror of third-party source corpora. |

The [dataset card](../training/dataset/observational/DATASET-CARD.md) documents
collection, intended use, split controls, limitations, privacy, and licensing
boundaries.

Third-party datasets are referenced at their official repositories and pinned
revisions rather than copied into Mini Gibson. Model weights and private
credentials are not published. The Gibson Bench task packages are visible in
the public repository, but the registered 35-task final evaluation remains
operationally sealed: it has not been read or run by the final model-comparison
pipeline.

## Used only in the successor compatibility preflight

| Component | Exact source | Boundary |
| --- | --- | --- |
| SWE-rebench V2 | [dataset](https://huggingface.co/datasets/nebius/SWE-rebench-V2), revision `10483de0f50fe5da545942705a76c6150171af7f` | Source for the frozen 456-task compatibility matrix. It was not used for successor model training or scoring. |
| SWE-rebench V2 tooling | [SWE-rebench/SWE-rebench-V2](https://github.com/SWE-rebench/SWE-rebench-V2) | Reference task-construction and evaluation tooling. |

The separate, publicly visible 35-task Gibson Bench final holdout remains
operationally sealed and unconsumed by the model-comparison pipeline.
Its source repositories are
[ConferenceOS](https://github.com/The-AIE/conference-os) (22 tasks, private),
[The Gibson](https://github.com/The-AIE/the-gibson) (8 tasks, public), and
[Chatterbuilt](https://github.com/The-AIE/chatterbuilt) (5 tasks, private).
The private sources require repository access and are not public submission
dependencies.

## Official Nemotron references

These are authoritative reference projects, not claimed runtime dependencies
of the completed experiment:

- [NVIDIA-NeMo/Nemotron](https://github.com/NVIDIA-NeMo/Nemotron)
- [NVIDIA-NeMo/Megatron-Bridge](https://github.com/NVIDIA-NeMo/Megatron-Bridge)

## Completed 7B rehearsal and runtime reference

These components supported the separately documented 7B rehearsal and endpoint
check. They did not produce the completed 30B v1 paired result:

| Status | Component | Role |
| --- | --- | --- |
| Completed, not scored | [OpenCodeReasoning-Nemotron-7B](https://huggingface.co/nvidia/OpenCodeReasoning-Nemotron-7B), revision `3baa2a3d73bbca12483ad19fef7babdcb2222987` | 20-step LoRA pipeline rehearsal on Brev. |
| Development runtime | [vLLM](https://github.com/vllm-project/vllm) | Served the 7B rehearsal for endpoint and required-tool checks; the first real-repository coding task did not apply an edit. |

## Proposed next training data

These sources were not used in the completed v1 result or the successor
compatibility preflight:

| Status | Source |
| --- | --- |
| Proposed next | [SWE-rebench OpenHands trajectories](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories), revision `35455389ab51bf5e2306bfd436ef72d0f98bf882` |
| Proposed next | [Scale-SWE Distilled](https://huggingface.co/datasets/AweAI-Team/Scale-SWE-Distilled), revision `c14ce2130f494812fef907f4afc81d8e33990805`; [source repository](https://github.com/AweAI-Team/ScaleSWE) |
| Proposed auxiliary only | [SWE-smith Python](https://huggingface.co/datasets/SWE-bench/SWE-smith-py), revision `77cab9055d42ab4a5c25c89a8f937096db13558e`; [source repository](https://github.com/SWE-bench/SWE-smith) |
| Proposed diversity source | [SWE-bench-extra](https://huggingface.co/datasets/nebius/SWE-bench-extra) with [SWE-agent trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) | Requires action-schema conversion and a new exclusion review before use. |
| Deferred edit prior | [CommitPackFT](https://huggingface.co/datasets/bigcode/commitpackft) | Large single-file commit corpus; useful as an edit prior, but not a substitute for repository exploration and test-recovery trajectories. |

Any next run needs a new preregistered protocol, fresh development tasks, and a
training-exclusion check before these sources can be selected.

## Planned post-run analysis

These tools did not participate in scored runs or the compatibility preflight:

| Tool | Official links | Planned role |
| --- | --- | --- |
| Langfuse | [repository](https://github.com/langfuse/langfuse), [documentation](https://langfuse.com/docs) | Redacted trace analysis after immutable local results are finalized. |
| Jev / TypeSafe | [product](https://typesafe.ai/), [quickstart](https://docs.typesafe.ai/introduction/quickstart), [API](https://docs.typesafe.ai/api), [Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python), [agent skill](https://github.com/typesafe-ai/skills) | Bounded, post-run anomaly classification that cannot change scores or authorize retries. |
| NeMo Gym | [NVIDIA-NeMo/Gym](https://github.com/NVIDIA-NeMo/Gym) | Proposed repeatable experiment orchestration; it did not participate in the completed runs. |

Jev is a hosted proprietary model. The linked TypeSafe repositories contain
official integration code, not the Jev model source.
