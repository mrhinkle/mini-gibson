# Deliverables

## Product
- Reproducible Mini Gibson training and evaluation pipeline.
- Frozen experiment manifests, bounded runners, and tamper-evident receipts.
- GibsonEnv and its agent adapter contract.
- Training-data provenance, exclusion controls, and promotion gates.
- Brev recovery and resumability package.
- Experimental specialized adapter, retained as evidence but not promoted.

The deliverable is the pipeline for improving and measuring coding-agent
outcomes, not a claim that the current adapter is production-ready. The project
and source repositories are indexed in [PROJECT-MAP.md](PROJECT-MAP.md).

## Data
- Historical trajectory manifest with provenance.
- Gold trajectory set.
- Frozen train/validation/temporal/external split.
- Nemotron-compatible SFT records.

## Evidence
- Completed v1 base-versus-tuned development comparison.
- Verified no-promotion decision, including malformed-response safety evidence.
- Full 456-task successor compatibility journal and matrix at the registered
  terminal boundary.
- Failure taxonomy and immutable run receipts.
- Verified terminal report, limitations, hashes, and cost record.

## Presentation
- Recorded 3:44 demo with a terminal-evidence card.
- Editable six-slide final-findings deck.
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
