# Real-repository evaluation

This package is the entry point for the new SWE-rebench V2 development cohort.
It does not open or execute the 35 Gibson Bench v0.1 final holdouts.

`candidates.py` consumes a JSONL export of the upstream dataset pinned at
revision `10483de0f50fe5da545942705a76c6150171af7f`. It emits a deterministic,
non-runnable candidate report. A candidate report deliberately has no image
digest, AST fingerprint, hidden verifier package, or qualification receipt.

```bash
python -m evaluation.candidates \
  --records /path/to/pinned-swe-rebench-v2.jsonl \
  --registry /path/to/exclusion-registry.json \
  --mode pilot \
  --seed 414 \
  --output /path/to/pilot-candidates.json
```

`cohort.py` validates a fully qualified lock. `load_and_validate_lock` is the
required scored-run entry point because it hashes the exact exclusion-registry
and sealed-verifier-package bytes before returning an allowlisted task
projection. The Python checks are authoritative; the JSON Schemas document the
wire format but cannot express repository diversity, statement leakage, or
cross-file hash binding on their own.

`sequential.py` preregisters the bounded evidence-collection sequence without
optional stopping: a disjoint 24-task budget pilot followed by three disjoint
144-task development cohorts. It freezes all 456 candidate identities before
v2 training-row selection or scored outcomes, finalizes a training exclusion
registry only after every qualified lock supplies all fingerprints, and assesses
the fixed cumulative looks at N=144/288/432. See
[`docs/sequential-development-evaluation.md`](../docs/sequential-development-evaluation.md).

The hardened Docker broker and receipt verifier are now wrapped by
`python -m evaluation.qualify_candidates`. The wrapper verifies the frozen
plan, exclusions, evidence and exact pinned Parquet before any run; seals image,
parser, verifier and task-material hashes; journals each complete two-by-two
qualification with an fsynced hash chain; and resumes without reclassifying a
prior row. See the
[qualification runbook](../docs/rebench-qualification-runbook.md). No candidate
report becomes a runnable lock until all 456 receipts qualify.

## Frozen 2026-10-17 candidate sequence

The outcome-blind pilot plus development A/B/C candidate sequence is committed
under
[`frozen/mini-gibson-v2-sequential-2026-10-17/`](frozen/mini-gibson-v2-sequential-2026-10-17/).

Build its outcome-blind sealed material package and immutable image lock first
with `python -m evaluation.prepare_qualification_materials`. The preparation
command uses bounded, resumable metadata caches, authenticates GitHub reads via
the `gh` CLI, resolves registry manifests without pulling image layers, and
does not read the final holdout. See
[`docs/rebench-qualification-runbook.md`](../docs/rebench-qualification-runbook.md).
It binds the exact public Parquet revision and SHA-256, the pre-plan exclusion
registry, all 456 ordered task IDs and public fingerprints, and the candidate
selector/validator/schema source hashes. The committed reports are still
non-runnable: immutable image digests, AST-edit fingerprints, executed parser
source hashes, sealed verifier bytes, and two-by-two qualification receipts
remain required before an execution freeze can be finalized.

Regenerate from the exact pinned Parquet bytes with an environment that has
`pyarrow` installed:

```bash
python -m evaluation.freeze_real_cohorts \
  --parquet /bounded/path/train-00000-of-00001.parquet \
  --output-dir evaluation/frozen/mini-gibson-v2-sequential-2026-10-17 \
  --repo-root .
```

The command reads only the twelve eligibility/provenance columns listed in the
freeze evidence and does not inspect model outcomes. It does not read or run
the 35-task Gibson Bench final holdout; the stronger repository boundary in the
committed v1 training manifest excludes all three internal holdout repositories.
