# NeMo Gym: Mini Gibson feasibility smoke

This is a **working, non-scored NeMo Gym integration**, not the evaluator used
for the completed Nemotron comparison. It exercises the failure mode we need
to improve next: malformed tool calls. The synthetic verifier gives `1.0` only
to one `apply_patch` function call with a JSON `patch` argument and basic patch
framing; malformed arguments and model-authored claims of `VERIFIED` get `0.0`.
It never applies a patch, runs tests, calls a model, or reads a benchmark task.
**Do not use this format-only reward as an issue-resolution or training reward.**
GibsonEnv's independent, networkless execution receipt remains the authority
for actual software-engineering outcomes.

## What we ran on October 18, 2026

- Upstream: [NVIDIA-NeMo/Gym](https://github.com/NVIDIA-NeMo/Gym), v0.7.0 at
  `1f8afc71d45fac14872d86fe300374afa2001e7a`.
- Runtime: CPython 3.13.14 on macOS arm64; NeMo Gym reported v0.7.0.
- Upstream verifier/session example: `gym env test --resources-server
  example_single_tool_call` — **5 passed**.
- This repository's synthetic verifier: `gym env test --resources-server
  mini_gibson_tool_call --search-dir <absolute-path-to-mini-gibson>/integrations/nemo_gym`
  — **1 passed**, including four verifier cases (valid call, malformed JSON,
  model self-award, missing response).
- No API key, remote model, GPU, scored task, or final holdout was used.

The Gym CLI's `--search-dir` finds this external resources server. The test
uses the official verifier-fixture API. These results demonstrate that the
format-checking component can run in Gym; they **do not** demonstrate a
Nemotron rollout, an RL fine-tune, or improved issue resolution.

## Reproduce

From a separate checkout of the pinned upstream Gym revision, install the
locked Gym environment with Python 3.13.14, then run:

```bash
gym env test --resources-server example_single_tool_call
gym env test --resources-server mini_gibson_tool_call \
  --search-dir /absolute/path/to/mini-gibson/integrations/nemo_gym
```

Use the `gym` executable from that pinned Gym environment. The second command
creates an isolated environment for this resources server using its
`requirements.txt`. Its only dataset is the checked-in synthetic verifier
fixture. Upstream instructions for [building an environment](https://docs.nvidia.com/nemo/gym/v0.7.0/environment-tutorials/single-step-environment/)
and [the CLI](https://docs.nvidia.com/nemo/gym/v0.7.0/reference/cli-commands/)
describe the underlying contract.

## Responsible next integration

After the frozen successor compatibility gate is resolved, a **newly
preregistered** experiment could use Gym to collect tool-use rollouts and
test a richer reward adapter. That adapter must require hash-bound GibsonEnv
receipts, reject self-reported success, and preserve identical budgets and
tool schemas across base and tuned arms. Keep the 35-task final holdout sealed
until all development gates pass. This integration does not change any
completed or running experiment.
