# Nemotron 3.5 Lightning × OpenHands evidence

This directory is the public, reproducible evidence package for the 17 October 2026 Mini-Gibson fine-tuning experiment.

The tuned adapter resolved more development issues than the base model, but the fixed 48-task evaluation did **not** establish a reliable overall advantage. The cumulative result was 16/48 versus 9/48, with 12 tuned-only wins, 5 base-only wins, and a one-sided exact paired p-value of 0.0717. Tool-call reliability also regressed materially: malformed responses affected 21/48 tuned tasks versus 8/48 base tasks.

Start with:

- [REPORT.md](REPORT.md) — the one-page evidence sheet and conclusion.
- [figures/effect-estimates.svg](figures/effect-estimates.svg) — directly labeled effect estimates.
- [summary.json](summary.json) — machine-readable outcomes and provenance.
- [DATASET-STRATEGY.md](DATASET-STRATEGY.md) — recommended next training-data mix.
- [diagnostics/token-cap/REPORT.md](diagnostics/token-cap/REPORT.md) — bounded 512→1024→1536 truncation diagnosis; it does not replace the frozen comparison.
- [verify_evidence.py](verify_evidence.py) — standard-library integrity and outcome verification.
- [SHA256SUMS](SHA256SUMS) — immutable file hashes, generated after packaging.

## Included data

- Four complete JSONL result files: base and tuned arms for both 24-task stages.
- All 48 public synthetic development fixtures.
- Frozen evaluator source and locks for both stages.
- The exact fine-tuning configuration and the recovered training-data manifest whose hash is attested in every tuned evaluation row.
- The post-study token-cap diagnostic, including exact evaluator variants, locks, complete result rows, and an independent verifier.
- Training and adapter provenance, but not model weights.

## Deliberately excluded

- Adapter weights and base-model weights.
- Raw upstream training trajectories and caches.
- Private reference solutions and untouched final-holdout tasks.
- Credentials, provider state, and machine-specific secrets.
- The invalidated v6 evaluation, whose snapshot checker incorrectly counted `.pytest_cache` as an unauthorized change.

## Verify

From the repository root:

```bash
python3 docs/evidence/lightning-openhands-2026-10-17/verify_evidence.py
```

The verifier checks file hashes, pair alignment, fixture hashes, safety invariants, success counts, paired wins/losses, exact one-sided p-values, and malformed-response counts.
