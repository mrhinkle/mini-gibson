# Mini-Gibson successor experiment protocol

Frozen: 2026-10-18, before successor execution.

## Why this is a successor experiment

The predecessor qualification stopped after its first immutable receipt. The
task image was actually clean, but the evaluator forced verifier containers to
UID/GID `1000:1000` while the repository and Git index in that image were owned
by root. Git rejected the checkout as dubious ownership. The archived stderr
SHA-256 is
`ff8031ba05e92e3ef9bda9f2cf3028f768863e77e537c1597ee50fdef90a9a73`.
That receipt remains terminal evidence for the predecessor and will not be
deleted, edited, or selectively rerun.

The successor changes evaluator mechanics, so it receives a new experiment
identity, source revision, hash-chained journal, and final manifest. It does not
continue the predecessor journal.

## Fixed candidate universe

The candidate universe remains the already frozen, disjoint 456-task plan:

- 24 budget-pilot tasks;
- development cohorts A, B, and C, 144 tasks each;
- SWE-rebench V2 revision
  `10483de0f50fe5da545942705a76c6150171af7f`;
- Parquet SHA-256
  `0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`;
- canonical sequential-plan SHA-256
  `961ee3c99b89248316f34dcbf8b30caa32291aebb5b239f8a2523634abbd6427`.

No task is added, removed, substituted, or re-ranked because of predecessor
behavior. The 35-task Gibson Bench v0.1 final holdout remains sealed and is not
read or run by this preflight.

## Evaluator repair

Agent/model commands remain forced to non-root UID/GID `1000:1000`. Verifier
commands instead inherit the immutable image's configured user and home, as the
upstream SWE-rebench images bind repository ownership, editable installs,
toolchains, and caches to that identity. Verifier containers remain fresh and
disposable with:

- immutable digest-pinned images;
- no network;
- no host mounts or Docker socket;
- all capabilities dropped;
- `no-new-privileges`;
- bounded CPU, memory, PIDs, time, and captured output;
- exact frozen base-commit validation before patching;
- protected-test integrity validation.

## Phase 1: outcome-blind compatibility preflight

All 456 tasks receive exactly two fresh verifier-container mechanics runs:

1. base checkout plus hidden test patch;
2. base checkout plus gold product patch plus hidden test patch.

The actual test command is cryptographically recorded but replaced by the
literal command `true`. This phase does not run tests, parsers, models, agents,
or formal comparisons. It observes only repository identity, clean-state,
patch applicability, and protected-path integrity.

Each result is appended once to a fsynced SHA-256 chain. Incompatible results
do not stop the matrix and cannot be reclassified on resume.

Decision after all 456 receipts:

- If all 456 are compatible, freeze a new qualification protocol and journal.
- If any are incompatible, do not proceed with a 455-plus-one or other changed
  cohort. Either apply one generic, outcome-blind evaluator repair and rerun the
  entire 456-task preflight under another new identity, or abandon this cohort.

## Later phases, not authorized by preflight completion alone

After a 456/456 compatible preflight, successor qualification must run every
task once through two base-fail and two gold-pass test executions in fresh
networkless containers. Only a fully qualified 456-task freeze may be used to
build v2 training data and select the pilot turn budget.

The preregistered model comparison remains base versus v1 versus v2 at formal
development looks only at N=144, N=288, and N=432, using exact paired McNemar
local alpha 0.01/0.015/0.025, observed uplift of at least five percentage
points, and the existing futility, malformed-response, determinism, tamper,
isolation, and safety gates. There is no optional stopping or significance
chasing. The final holdout may open only if every development gate passes.

## Operations and stop rules

The durable controller runs one immutable image at a time, removes only that
exact image after its receipt, preserves its journal across interruption, and
uses an exclusive lock. Docker pull output is bounded and excluded from public
logs. Rate-limit retries are bounded. Execution stops on journal corruption,
input/hash disagreement, missing registry authentication, non-rate-limit pull
failure, controller output overflow, less than 32 GiB free storage, or any
isolation/integrity failure outside a valid per-task compatibility receipt.

The existing Brev A100x2 host is used at $3.96/hour, below the approved
$30/hour cap. The controller cannot create, stop, or delete compute.
