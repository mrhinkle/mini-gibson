# Mini-Gibson v2 overnight findings

**Evidence state:** live checkpoint; not the 07:00 ET freeze

**Current conclusion:** v2 unadjudicated; v1 remains not promotable

**Final holdout:** sealed and unconsumed

## Executive finding

The completed v1 experiment showed a promising issue-resolution gain but failed both the frozen statistical boundary and the reliability gate. The v2 experiment has a substantially stronger, outcome-blind design and is now executing, but no v2 model outcomes have yet been observed. Therefore the only scientifically complete conclusion remains: **fine-tuning may improve issue resolution, but the existing adapter is not a reliable or statistically established upgrade.**

## Completed v1 result

| Measure | Base | v1 tuned | Difference |
| --- | ---: | ---: | ---: |
| Resolved issues | 9/48 | 16/48 | +7 / +14.58 percentage points |
| Tuned-only / base-only paired wins | — | 12 / 5 | one-sided exact p=0.0717316 |
| Tasks with malformed responses | 8/48 | 21/48 | tuned worse; p=0.000488 |

The issue-resolution effect was directional, not statistically established. The malformed-response regression is a promotion-blocking safety result.

## Frozen v2 design

- Source: `nebius/SWE-rebench-V2` revision `10483de0f50fe5da545942705a76c6150171af7f`.
- Source Parquet SHA-256: `0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`.
- Frozen tasks: 24 pilot plus three disjoint development cohorts of 144, for 456 total candidates.
- Formal looks: cumulative development `N=144`, `N=288`, and `N=432` only.
- Local one-sided exact paired McNemar alpha: `0.01`, `0.015`, and `0.025`.
- Efficacy also requires at least `+5` percentage points observed uplift and every frozen reliability, malformed-response, tamper, isolation, parser, and receipt gate.
- Stop at registered efficacy, futility, safety failure, or `N=432`; do not add tasks or selectively repeat runs to obtain significance.

## Current execution checkpoint

At the latest verified live checkpoint, Brev instance `weird-white-ocelot` (`ds7uiptfk`) was `RUNNING`, `HEALTHY`, and shell-ready with two NVIDIA A100 80 GB GPUs at `$3.96/hour`. The approved total cap remains `$30/hour`.

The authenticated, independently reviewed preparation controller preserved the 199 anonymous-cache records and advanced the immutable image-metadata cache to 398 of 456. A live Docker token check proved that the account token had a nonempty authenticated subject and pull permission, but Docker enforced a 200-pull hourly window and returned a misleading anonymous-limit message. The billing page for the browser-authenticated account showed no active subscription. The controller now waits and resumes through that bounded window without discarding the cache.

The rolling qualification controller remained armed behind the two preparation-complete markers and now inherits the same private Docker authentication. Qualification receipts: 0/456. No v2 training, pilot, development look, or final-holdout outcome had occurred.

## Decision boundary at the reporting cutoff

By 07:00 America/New_York this report will state one of the following, using only the frozen assessor and verified receipts:

1. preregistered development success;
2. preregistered futility or maximum-N non-promotion;
3. terminal safety failure;
4. terminal qualification/execution failure; or
5. incomplete at cutoff, with the exact completed stage and no manufactured v2 conclusion.

If qualification is incomplete, the new overnight evidence is operational rather than evidence about the model hypothesis. If training is incomplete, v2 is not a completed adapter. Before `N=144`, any development outcomes are diagnostics, not a formal look.

## Repository and reproducibility status

- GitHub main at experiment start: `fdd362909ea90d8055781b19167f9d0273b8362e`.
- Reviewed installed source: `700e1596559b86df5ddfac2eef5dd1c70bab0abb`.
- Installed source diff SHA-256: `f83b1db48197e7eb6fea6bfa5e6edbc3c461ba2d7d8f7aec6a5d1865f5579595`.
- Preparation controller SHA-256: `aaa7c777c2db35eff0ec97567309629094cf1bd24ea7984c1a4f9f421cac940e`.
- Preparation body SHA-256: `c0f90a05ab3e891e93205842e866608528bd8562ec71eb292ef48e0152f21754`.
- Qualification controller SHA-256: `df30fefa0b5983bb262567f171f3f5684e6df210759d4f884be804d20b0bec17`.
- Final holdout: sealed and unconsumed.

The repository currently lacks the owner-approved `.fleet-gate` bootstrap required by the global pre-push hook. The experiment must not bypass that hook. If publication remains blocked at the deadline, the exact local evidence commit, complete Git bundle, patch, and hashes will be archived under the durable remote root.
