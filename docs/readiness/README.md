# Readiness handoff

Updated 2026-10-16. This index consolidates the implementation and preserves the
prior discovery notes. The private corpus and generated training artifacts stay
outside Git. No GPU launch, weight download, publication or organizer message is
authorized by these files.

## Current implementation

- [Data preparation](../readiness-data-preparation.md): exact-token packing,
  complete tool batches, assistant-only labels, provenance and completion seals.
- [Trainer interface](../readiness-trainer-interface.md): convert saved labels to
  next-token targets and a separate loss mask, without treating CPU conversion as
  proof of the real training-container loader.
- `requirements-tokenization.txt`: pinned CPU preparation dependencies.
- `python -m training.historical.prepare --help`: preparation interface.
- `python -m inference.smoke --help`: offline fixture mode by default; live mode
  requires an explicit endpoint. A tool-format probe is not a scored repair.

From a matching CPU environment, local checks are:

```bash
python -m pytest tests/historical tests/runtime tests/evaluation tests/bench -q
python -m unittest discover -v
```

In an already approved, matching training container, the first provider check is:

```bash
python -m training.container_provider_smoke
```

That check uses temporary synthetic token rows. It does not load weights, train,
or establish acceptance of the private export. The actual private loader,
finite-loss optimizer step, checkpoint save/resume, merge/export and distinct
vLLM serving checks remain to execute. No verified custom-data training command
or completed A/B/C result is claimed here.

Benchmark PR #14 is merged. The experiment controls and tool/runtime contract
still require the design freeze in The-AIE/the-gibson#417. The GPU rehearsal
remains on hold until Mark authorizes the instance and container. The corpus
remains private, and eligibility/publication clarification remains unresolved.

## Archived discovery and candidate notes

These are dated snapshots, not current commands or approved experiment settings:

- [Pipeline audit](archive/2026-10-15/readiness-pipeline-audit.md)
- [GPU rehearsal research](archive/2026-10-15/readiness-gpu-rehearsal.md)
- [Initial data specification](archive/2026-10-15/readiness-data-spec.md)
- [Experiment candidate](archive/2026-10-15/readiness-experiment-candidate.md)

Each snapshot carries a superseded header. Current guides take precedence over
old filenames, pre-export counts, strict-order proposals and candidate pins.

## Archived code package

The [October 15 source overlay](archive/2026-10-15/mini-gibson-readiness-code.zip)
is preserved as a public-safe archive. All 11 source files and the code hash
manifest are byte-identical to the reviewed package and current main. The README
retains dated context, with private host paths and corpus fingerprints removed.
The archive has no corpus, token arrays, private session logs, weights or
credentials. Its overlay instructions are historical; use the current guides
above instead of applying it over main.
