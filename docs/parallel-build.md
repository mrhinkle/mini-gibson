# Two-Coder Parallel Build

## Goal

Compress Mini Gibson implementation by using two coding agents in parallel without allowing them to create conflicting architecture.

## Coder 1 — Codex: Runtime / Control Plane

Codex owns the executable orchestration layer:

- manifest parser and validator;
- experiment lifecycle;
- GibsonEnv integration;
- Agent Adapter interface;
- Hermes reference adapter;
- Evidence Gate;
- supervisor/checkpoint/resume;
- telemetry/run artifacts;
- CLI;
- runtime tests.

**Exclusive scope:** `experiment/**`, `gibson_env/**`, `adapters/**`, `cli/**`, `telemetry/**`, `tests/runtime/**`.

Codex does not edit benchmark definitions, training data, Brev, vLLM, reports, presentation, or shared design files.

## Coder 2 — Grok: Data / Infra / Evaluation

Grok owns the reproducibility and measurement layer:

- vLLM setup;
- Brev Launchable;
- historical trajectory validation/conversion;
- Gibson Bench fixture/schema/scoring;
- failure taxonomy tooling;
- report generation;
- presentation data generation;
- evaluation/infrastructure tests.

**Exclusive scope:** `bench/**`, `training/**`, `vllm/**`, `brev/**`, `env/**`, `report/**`, `presentation/**`, `scripts/infra/**`, `scripts/data/**`, `tests/evaluation/**`.

Grok does not edit runtime/control-plane or shared design files.

## Integrator — Claude

Claude owns shared interfaces and integration only:

- `README.md`
- `PLAN.md`
- `HYPOTHESIS.md`
- `experiment.example.yaml`
- `pyproject.toml`
- architecture/protocol/conformance docs

Claude also performs independent cross-lane review.

The integrator must not silently rewrite lane results. Interface changes are recorded and both lanes are revalidated.

## Why this split

The split follows a stable architectural seam:

```
        RUNTIME / CONTROL PLANE
            Codex lane
                |
                | immutable run artifacts
                v
        DATA / EVALUATION / INFRA
             Grok lane
```

The contract between lanes is the run artifact schema and experiment manifest, not shared source files.

## Working method

Each coder gets:
- separate branch/worktree;
- exclusive file scope;
- explicit acceptance tests;
- no authority over shared files;
- exact-head handoff receipt.

Each lane returns:
- exact head SHA;
- changed files;
- tests;
- acceptance results;
- unresolved risks;
- integration notes.

## Integration gates

### Gate 0 — Design freeze
Do not start interface-heavy implementation until the Kimi/GLM/Claude design freeze resolves the baseline, manifest, and conformance contract.

### Gate 1 — Lane smoke
Each lane passes its own acceptance tests independently.

### Gate 2 — Combined smoke
Reference agent → vLLM → GibsonEnv → real tool → Evidence Gate → immutable result.

### Gate 3 — Benchmark freeze
Only after combined smoke is stable.

### Gate 4 — A/B evidence
Historical LoRA remains optional until A/B works.

## Schedule compression

With two independent lanes, roughly 35–50 coding hours should compress substantially because the runtime/control-plane and data/infra/evaluation work can progress concurrently.

Do not optimize for maximum parallelism. Optimize for **zero merge collisions and clear experimental provenance**.

## Optional Jev responsibilities

Jev remains disabled by default and is cuttable without blocking the primary experiment. Mark/Codex owns `adapters/jev.py`, `experiment/manifest.py`, `experiment/decisions.py`, `telemetry/jev.py`, the metadata-only GibsonEnv tool-risk connection, and their runtime tests. This includes environment-only credentials, the pinned typed-question API, deterministic fallback, and fail-closed identical-arm manifest validation.

John/Grok owns future anomaly-hook calls from redacted recorded result summaries and metadata consumption in reports: latency, confidence/fallback/error counts and policy hashes. Advice follows immutable outcomes and never changes scores, promotes adapters or exposes holdouts. Supervisor and benchmark runners do not yet exist; their Jev hooks are exported and the owning lane wires them when those runners are implemented.

Claude remains the independent exact-head reviewer and coordinates shared question/policy/artifact version changes. `integrations/jev.yaml`, `docs/jev.md`, the workflow manifests, example configuration and shared protocol documentation describe this optional interface. Updates to those shared contracts require a bounded owner-approved integration change; routine worker shared-file prohibitions and broader design/benchmark freeze gates remain in force. See [the Jev contract](jev.md) for configuration, implemented limits and acceptance criteria.
