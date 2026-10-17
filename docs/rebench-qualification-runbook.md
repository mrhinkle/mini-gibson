# SWE-rebench qualification runbook

This checkpoint qualifies the already-frozen 456-task sequence. It is not a
model evaluation and never opens the 35-task Gibson Bench final holdout.

## Inputs

The runner requires the exact pinned SWE-rebench V2 Parquet bytes (SHA-256
`0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`), a
sealed material tar, and an image lock. The tar contains only
`materials.json` plus the parser members declared in its `parser_files` map.
Its 456 material rows must be in frozen candidate order and must exactly match
the task, test, patch, and install fields in the pinned Parquet. The image lock
must name the same 456 tags in the same order and bind each to a
`name@sha256:...` reference and repository workdir.

Before any container starts, the command validates the committed plan,
pre-plan exclusion registry, freeze evidence, dataset bytes/revision/row count,
material package, parser source hashes, and image lock. Immediately before each
qualification it uses read-only `docker image inspect` to confirm that the
locked digest is locally present for `linux/amd64`. The Docker backend itself
uses `--pull never` and `--network none`.

## Dry run

```bash
python -m evaluation.qualify_candidates \
  --dataset /bounded/pinned/train-00000-of-00001.parquet \
  --material-package /bounded/sealed/qualification-materials.tar \
  --image-lock /bounded/sealed/image-lock.json \
  --journal /bounded/state/qualification.jsonl \
  --output-dir /bounded/state/final \
  --dry-run
```

Dry-run performs no Docker pulls, image inspections, or container runs. It
validates all supplied bytes, audits an existing journal read-only, and reports
that local image verification remains an execution-time blocker.

## Resumable run

Remove `--dry-run` to qualify. Each candidate receives exactly two fresh base
checks and two fresh gold checks through the networkless verifier. One complete
receipt is appended with `O_APPEND`, then `fsync`, and linked to the previous
record by SHA-256. A valid prior row is terminal and is skipped on resume,
including a valid unqualified row; the tool never reruns it into a different
classification. A partial final line, duplicate task, receipt mutation,
incomplete receipt, changed invariant, or broken chain stops the run.

`--limit N` bounds one invocation without changing the frozen order. It is
useful for small operational batches; resume with the same inputs and journal.
No qualified locks or execution-freeze manifest are created until all 456
receipts are valid and qualified. At that point the tool atomically writes the
four cohort locks, complete training-exclusion registry, pre-outcome execution
freeze, and `qualification-final-manifest.json`.

The final manifest explicitly records that no formal model outcomes were
observed and the final holdout remained sealed.
