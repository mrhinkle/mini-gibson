# Supervisor Protocol

## Purpose

Keep long benchmark/training runs healthy without biasing results.

## Responsibilities

- environment/model-server health;
- agent process heartbeat;
- task/run state;
- checkpointing;
- immutable run IDs;
- infrastructure retry;
- resume;
- telemetry persistence;
- stop conditions.

## Never do

- silently retry model/task failures;
- alter prompts after seeing holdout results;
- change budgets mid-run;
- drop failed trials;
- repair benchmark fixtures during a scored run.

## Failure classes

### Infrastructure
Examples: GPU node loss, vLLM crash, network interruption before task execution. Retry only under frozen policy and preserve failed infrastructure receipt.

### Task/model
Examples: bad patch, exhausted repair budget, invalid tool sequence, failed verification. Score as outcome; do not erase via retry.

## Run identity

Every run records an immutable run ID and copies the effective manifest, revisions, benchmark hash, environment receipt, task traces, evidence, and results.

## Resume

Resume only incomplete tasks after verifying existing receipts. Never overwrite completed trial artifacts.

## Optional Jev advice

The exported `DecisionService.supervisor_advice` hook accepts only infrastructure health, failure kind, whether execution started, existing retry eligibility, and retry count. The supervisor runner is not implemented in this foundation. Mark/Codex owns future hook placement and must retain deterministic health/retry/stop authority. Advice never executes a retry or changes the recorded outcome. A retry recommendation is rejected unless an unhealthy, pre-execution infrastructure failure already satisfies the declared retry policy.

`routing_advice` suggests the human/operator destination of an escalation only in an explicit `run.scored: false` context. It cannot switch Nemotron, generate code, change permissions, or decide adapter promotion, and is always excluded in scored mode.

Jev is disabled by default. Missing scoring context is treated as scored, and default scored policy returns fallback without a remote request. Optional identical-arm mode requires the frozen comparison validation in [the Jev contract](jev.md). Unavailable, invalid, or low-confidence advice falls back to human escalation/high risk; a telemetry failure also prevents remote advice from being consumed. The operator must retain the same retry budgets and report every failed trial.
