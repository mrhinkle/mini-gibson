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
