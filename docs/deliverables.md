# Deliverables

## Product
- Mini Gibson specialized adapter (conditional on promotion gate).
- GibsonEnv.
- Experiment manifest and runner.
- Agent adapter contract.
- Brev Launchable.

## Data
- Historical trajectory manifest with provenance.
- Gold trajectory set.
- Frozen train/validation/temporal/external split.
- Nemotron-compatible SFT records.

## Evidence
- Raw baseline run.
- Gibson Harness run.
- Historical-learning run if adapter promoted.
- Failure taxonomy.
- Immutable run receipts.
- Comparative report.

## Presentation
- 3–5 minute live demo.
- Six-slide maximum presentation.
- Backup recorded trace.
- Judge story.
- Technical report.

## Reproducibility package
Every final result records:
- Git SHA;
- base model repo + revision;
- adapter repo + revision;
- dataset revision/hash;
- benchmark manifest hash;
- vLLM version;
- training stack revision;
- GPU/hardware;
- inference settings;
- run policy.
