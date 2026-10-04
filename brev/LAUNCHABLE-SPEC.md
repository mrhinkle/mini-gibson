# Brev Launchable Specification

A fresh Launchable must recreate the validated Mini Gibson environment and pass the environment doctor without undocumented manual installation.

It must record/pin:
- Mini Gibson Git SHA;
- GPU profile;
- CUDA/driver-compatible base;
- vLLM version;
- training-stack revision;
- model revision;
- ports and workspace paths.

Secrets are injected at runtime, never embedded.

Profiles:
- **dev-inference:** cheapest proven stable configuration.
- **lora-training:** begin with NVIDIA's verified Nemotron 3.5 Lightning LoRA reference configuration.

The Launchable is not accepted until a fresh instance passes doctor plus a model/tool smoke task.
