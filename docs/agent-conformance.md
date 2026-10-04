# Agent Adapter Conformance v0.1 — DRAFT

An agent runtime must pass conformance before participating in causal cross-agent comparisons.

## Required interface

Conceptually:
- initialize(manifest, task)
- next_action(observation)
- receive_result(result)
- request_completion()
- shutdown()

## Required controls

A conformant runtime must:
- receive the standardized task;
- use the declared model endpoint for controlled runs;
- use only declared tool schemas/permissions;
- obey frozen step/context/time budgets;
- expose required telemetry;
- have no benchmark-answer access;
- have no undeclared model/provider calls;
- accept Gibson completion authority;
- terminate deterministically under the run policy.

## Classification

Each candidate runtime receives one status:
- CONTROLLED_CONFORMANT
- ECOLOGICAL_ONLY
- BUILD_REVIEW_WORKER
- NOT_SUPPORTED

Hermes / Claude Code / Codex / Grok classifications remain UNFROZEN pending #417 and implementation tests.

If a runtime cannot be forced to use the same Nemotron endpoint and tool contract, do not pretend it is an interchangeable causal-control agent. It may still be valuable as an ecological-validity comparison or build/review worker.
