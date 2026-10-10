# Handoff: self-improving-agents package (2026-10-04)

Reference material folded in from Mark's `mini-gibson-handoff-2026-10-04.zip`. Nothing here is on the
runtime path. Lanes port what they need into their own exclusive paths.

| File | Disposition | Owner |
|---|---|---|
| `REVIEW.md` | Claude's review of the handoff against the live repos and both machines | — |
| `verify.py`, `tests/`, `fixtures/` | Deterministic sensors (test-file checksums, harness-owned test rerun). Port into the Evidence Gate under `experiment/` | Lane A (Codex) |
| `eval_sensor.py` | Precision/recall of an advisory sensor on labeled incidents, by confidence band. Reusable against the Jev adapter from PR #7 | Lane B |
| `DESIGN.md` | Verifier design and JevCI comparison | reference |
| `jev_sensor.py` | **Superseded** by PR #7 (`adapters/jev.py`), Mark's pick on 2026-10-04. Kept only for its five yes/no claim-vs-evidence questions | — |
| `flight-recorder-epic/` | Gibson-side live capture epic (`loop.sh` changes, Tier C). Not a hackathon P0: historical sessions cover the data need (see REVIEW §1). File later through the normal Gibson pipeline | Gibson / Carmack |

Data tooling from the package now lives in Lane B paths: `scripts/data/` and `tests/evaluation/`.
