# Real-repository development evaluation

Status: implementation candidate, 2026-10-17. This is a development-set plan;
the 35 Gibson Bench v0.1 final-holdout tasks remain sealed.

## Decision

Add a separate evaluator for real repositories instead of extending the 48-task
synthetic-fixture harness. Freeze 144 scored development tasks and a disjoint
24-task pilot from `nebius/SWE-rebench-V2` at dataset revision
`10483de0f50fe5da545942705a76c6150171af7f`. Use the pilot only to choose a
single 30- or 50-turn budget before any scored task runs.

The first implementation slice is deliberately smaller than a scored run:

1. define a strict, versioned cohort lock;
2. validate identity, provenance, image digests, cardinality, diversity, and
   contamination exclusions without opening private task material;
3. select reproducible candidate pools from the pinned upstream dataset;
4. qualify a small upstream sample with the future Docker backend;
5. freeze the final pilot and scored locks only after every candidate passes two
   repeated base-fails/gold-passes checks.

No candidate lock is evidence of model performance, and no task is scored until
its image digest and qualification receipt are frozen.

## Cohort contract

The internal lock is immutable experiment provenance, but it is **not** passed
to the model. A single loader creates a smaller agent projection from it. The
lock contains:

- dataset name and 40-character revision;
- deterministic selection policy and seed;
- exactly 24 `pilot` tasks or exactly 144 `development` tasks;
- task ID, repository, source PR and issue identities, 40-character base
  commit, problem statement, language, repository license, immutable image
  reference and digest, image platform and work directory;
- hashes of the upstream install configuration and public task projection;
- patch/test-patch, normalized issue-text, changed-file, AST-edit, and image
  cluster fingerprints;
- verifier timeout, sealed-verifier-package hash, exclusion-registry hash, and
  qualification-receipt hashes.

The lock must never contain the gold patch, test patch, fail-to-pass or
pass-to-pass IDs, PR description, LLM metadata, hints, or qualification logs.
Those stay in a separate sealed verifier package. The agent projection contains
only the task ID, repository checkout identity, problem statement, language,
and execution budget. It excludes source PR/issues and every fingerprint,
verifier, selection, qualification, and hidden-test field.

The validator fails closed unless all of these hold:

- schema and policy versions are recognized and unknown fields are absent;
- the dataset revision, selection seed, lock digest inputs, and task ordering
  are stable;
- every image is pinned as `reference@sha256:digest`, not by tag alone;
- task IDs, task projections, base commits, image digests, and qualification
  receipts are present and correctly formatted;
- no task ID, repository/base-commit pair, patch/test-patch hash, normalized
  issue-text hash, changed-file fingerprint, or AST-edit fingerprint intersects
  the frozen exclusion registry;
- no repository, source PR, source issue, base or merge commit, image/task
  cluster, episode, fork, or backport identity intersects the registry;
- the 144-task scored cohort spans at least eight languages and 24 repositories,
  with no more than eight tasks from one repository;
- the 24-task pilot is disjoint from the scored cohort and all training data;
- every task is labeled `pilot` or `development`, never `holdout`.

The selection-time exclusion registry covers the 48 completed synthetic
development fixtures, all 35 Gibson Bench v0.1 holdouts, the opposite real-task
cohort (pilot or scored), and every training instance used for the current or
future adapter. The registry is built once from private sources; it stores only
identities and cryptographic fingerprints, never holdout patch bytes. After a
cohort freezes, its entries are added to the registry used by every later data
or cohort selection. Training and evaluation are separated by repository and
image/task cluster, not only by trajectory-row ID. Adapter version labels are
not dataset names; every registry source names its exact release and manifest
hash.

The lock records the registry and sealed-package digests. The sole scored
entrypoint recomputes them, invokes this validator, and refuses mismatches. The
legacy fixture runners and `bench/verify.py` do not accept real-repository
cohort locks.

## Selection policy

Candidate selection is deterministic and operates on the pinned upstream
records. It excludes tasks that require network services, credentials,
databases, migrations, submodules, binary patches, destructive operations,
renames only, unsupported log parsers, or missing/high-risk licenses. It accepts
only tasks with non-empty issue descriptions, fail-to-pass tests, test commands,
parsers, install configurations, base commits, and image names.

After eligibility filtering, select with stable hashing while balancing:

- language and repository;
- upstream difficulty;
- changed-file and changed-line buckets;
- issue/feature category;
- expected test duration after qualification.

The generator writes a candidate report with all rejection counts. It does not
invent image digests or qualification receipts. Candidate tasks remain
`qualification_pending` until the Docker qualification lane fills those fields.
Candidate reports are not cohort locks and cannot be loaded by the runner.

Statement validation also scans the agent projection. It rejects fixing-PR
URLs/numbers, base or merge commits, declared test IDs, long gold-patch lines,
and registry-provided leakage tokens. A clean set of keys is insufficient when
the same hidden value is embedded in prose.

## Execution boundary

The trusted host orchestrator loads the pinned base model and arm-specific
adapter, but model-generated commands run only inside disposable task
containers. All task images and model weights are pre-pulled. Scored execution
is offline (`--network none`, `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`), non-root, capability-free, bounded by CPU, memory,
PID, command, verifier, and wall-clock limits, and receives no credentials,
proxy variables, host home, SSH agent, cloud metadata, hidden verifier files, or
Docker socket.

Verification uses a second fresh container. The host applies the candidate
patch and sealed test patch, then requires a zero test-command exit and complete
fail-to-pass/pass-to-pass success from a vendored, pinned parser. The upstream
runner is not used unchanged because its host-network and exit-status semantics
are insufficient for this experiment.

## Arms and frozen budget

Run one deterministic paired trial on identical ordered task IDs for:

- `base`: pinned Nemotron 3.5 Lightning base, no adapter;
- `v1`: the current adapter, pinned by config, weights, source, and export hashes;
- `v2`: the future adapter, pinned identically.

All arms use greedy decoding, `max_new_tokens=1536`, a 32,768-token input cap,
one scored attempt, 120-second shell calls, a 900-second verifier timeout,
1,800-second total task wall clock, and 12,000-character deterministic tool
observations plus a full-output hash. The 24-task pilot selects 30 or 50 turns
using a predeclared rule; the choice is frozen before the 144-task run.

## First-slice acceptance

- Unit tests demonstrate rejection of wrong cardinality, duplicates, unknown
  fields, mutable-only image tags, unsupported parsers, missing hashes,
  non-development splits, repository over-concentration, insufficient language
  or repository diversity, and exclusion-registry overlap.
- The single lock loader recomputes registry and sealed-package hashes, runs
  statement-leakage validation, and emits an allowlisted agent projection; the
  execution entrypoint cannot bypass it.
- A deterministic candidate selector can consume the pinned upstream record
  shape without exposing sealed fields in its public output.
- The candidate report records accepted/rejected counts and the exact source
  revision.
- A Docker-backed single-task qualification smoke is specified but is not
  reported as complete unless Docker is available and the pinned image passes
  base-fail/gold-pass checks twice.
- Existing repository tests remain green.

## Promotion boundary

Do not consume the 35-task final holdout, promote either adapter, or claim an
overall model improvement from this development cohort. Freeze promotion
thresholds and malformed-response/policy non-inferiority margins before the
scored development run. A separate explicit decision is required before the
final holdout is opened.
