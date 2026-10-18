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

## Prepare and seal the inputs

Install the CPU-only preparation dependencies, then run the builder from the
repository root. The cache must be durable across invocations. It contains only
public GitHub PR metadata, the exact pinned upstream parser bytes, and registry
image metadata; it contains no model outcomes or holdout material.

```bash
python -m pip install -r requirements-qualification.txt

python -m evaluation.prepare_qualification_materials \
  --dataset /bounded/pinned/train-00000-of-00001.parquet \
  --cache-dir /bounded/state/qualification-preparation-cache \
  --material-package /bounded/sealed/qualification-materials.tar \
  --image-lock /bounded/sealed/image-lock.json
```

The builder verifies the exact committed plan and 409 MiB Parquet SHA before
preparation. It obtains merge commits from authenticated GitHub PR metadata in
batches, caching each PR identity. If and only if GitHub reports an exact
PR-level `NOT_FOUND`, the builder may recover an exact two-parent
`Merge pull request #N from ...` commit from that authoritative repository;
the frozen base must be its branch-head ancestor and the authoritative diff
must exactly bind the frozen product and test patches. A separate transfer
fallback runs only on an exact repository-level `NOT_FOUND`: an authenticated,
complete frozen-base commit search must yield exactly one same-name repository
whose merged PR number, base commit, merge commit, and diff all match. Missing,
ambiguous, incomplete, or mismatched evidence fails closed, and every lookup is
bound into the resumable cache. The builder packages the unmodified
`lib/agent/log_parsers.py` bytes from SWE-rebench V2 revision
`c71902a8cf8d2b725f63d51f199f4d3e56f68d2d` and verifies Git blob
`51c2e178b392f36aedc3c64064a708498ff591f8` before hashing the executed bytes.
AST edit fingerprints are built from tree-sitter syntax trees over the exact
before/after source fragments reconstructed from each gold-patch hunk. Content
renames bind both paths.

Image resolution runs one `docker buildx imagetools inspect` metadata request
per uncached tag, selects exactly `linux/amd64`, and records the platform
manifest digest and image-config working directory. It never invokes
`docker pull` and never retains image layers. If GitHub or registry rate limits
interrupt the pass, rerun the same command and cache. Use
`--max-new-github-requests` or `--max-new-image-resolutions` to make each pass
smaller. No output artifact is emitted until every one of the 456 PR, AST,
parser, and image identities is resolved and both generated artifacts pass the
same strict readers used by qualification. Existing different output bytes are
never overwritten.

The success report must state `candidate_count: 456`, `docker_pulls: 0`,
`formal_model_outcomes_observed: false`, and
`final_holdout_status: sealed_not_read_or_run`. Record both artifact SHA-256
values before starting the dry run below.

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
