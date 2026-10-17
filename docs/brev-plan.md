# Brev Plan

## Deliverable

A fresh Brev Launchable recreates the validated Mini Gibson environment without undocumented manual package installation.

## Compute profiles

### Dev / inference
Smallest proven stable GPU configuration for the selected Nemotron serving precision.

### Training
Start from NVIDIA's verified Nemotron 3.5 Lightning LoRA configuration; optimize only after reference success.

## Launchable must pin/record

- source Git SHA;
- environment/container digest;
- CUDA/driver/Python/PyTorch;
- vLLM;
- training stack;
- model revision;
- ports;
- workspace paths;
- bootstrap/doctor command.

Secrets are injected at runtime, never embedded.

## First command

`gibson experiment doctor experiment.yaml`

The environment is not considered reproducible until a fresh Launchable passes doctor and a model/tool smoke task.

## Observed lifecycle constraint (2026-10-17)

The `hyperstack_H100x2` allocation used for the Lightning fine-tune did not support stop/resume. `brev stop mini-gibson-lightning-ft` returned `instance "mini-gibson-lightning-ft" does not support stop`, and the Brev web console exposed Delete—but no Stop or Suspend—in the instance actions.

Treat this as provider- and instance-type-specific evidence, not a permanent platform guarantee. Before a future launch that must pause without losing its disk, require a stoppable offering and verify the lifecycle controls before training. For a non-stoppable allocation, copy and hash required artifacts before requesting deletion; deletion is the only observed way to end that allocation.
