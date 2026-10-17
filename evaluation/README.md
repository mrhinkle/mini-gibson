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

The next implementation slice is a hardened Docker broker and repeated
base-fail/gold-pass qualification smoke on a small upstream sample. Until that
exists, no candidate report can become a frozen lock or a scored result.
