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
