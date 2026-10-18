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
- Active 456-task successor compatibility protocol and recovery record; full
  terminal matrix pending.
- Failure taxonomy and immutable run receipts.
- Verified v1 report and limitations; successor terminal hashes and cost pending.

## Presentation
- Recorded 3:30 demo; an updated findings card is drafted but not rendered.
- Editable six-slide interim findings deck; terminal counts pending.
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
