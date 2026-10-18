# Mini-Gibson v2 overnight findings

**Evidence state:** terminal qualification failure; frozen at `2026-10-18T03:18:02Z`

**Current conclusion:** the frozen v2 cohort was not executable; v2 remains unadjudicated and v1 remains not promotable

**Final holdout:** sealed and unconsumed

## Executive finding

The completed v1 experiment showed a promising issue-resolution gain but failed both the frozen statistical boundary and the reliability gate. The stronger v2 experiment stopped at its first preregistered qualification receipt, before training or model evaluation, because the first frozen image failed the verifier's clean-worktree precondition in all four repeats. Therefore v2 provides no new model evidence. The scientifically complete conclusion remains: **fine-tuning may improve issue resolution, but the existing adapter is not a reliable or statistically established upgrade, and this v2 run cannot adjudicate the hypothesis.**

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

## Terminal v2 result

At the terminal receipt, Brev instance `weird-white-ocelot` (`ds7uiptfk`) was `RUNNING`, `HEALTHY`, and shell-ready with two NVIDIA A100 80 GB GPUs at `$3.96/hour`. The approved total cap remained `$30/hour`.

The authenticated, independently reviewed preparation controller preserved its cache through Docker's bounded pull window and completed all 456 immutable image-metadata records. During sealing, the pinned dataset exposed legitimate multiline Gradle/JUnit test identifiers that the original single-line validator rejected. The smallest safe repair preserved embedded line feeds exactly while continuing to reject empty strings, NULs, carriage returns, and duplicates at every material, parser, and receipt boundary. The final diff passed 116 focused tests locally and on Brev, plus an independent Claude review with no blocking finding.

Preparation completed at `2026-10-18T03:16:37Z`. The sealed material package is 72,704,000 bytes with SHA-256 `380dc5246435877fd98db3a95dc65bf988f8b9f8109993c474bf841807414f8c`; the image lock is 160,378 bytes with SHA-256 `be030e93923feb4de9d57cbff9c4bcaa24e5d47eaf7654aa3e2ca3c69689323d`.

The exclusive controller then ran frozen pilot candidate 1, `natcap__invest-1365`. Its hash-valid receipt was unqualified:

| Boundary | Verified result |
| --- | --- |
| Frozen candidates prepared | 456/456 |
| Qualification receipts | 1/456 |
| Qualified receipts | 0 |
| Base-fail repeats | 0/2 |
| Gold-pass repeats | 0/2 |
| Repeat return codes | 84, 84, 84, 84 |
| Parser execution | valid in all four repeats |
| Integrity marker | missing in all four repeats |
| Training | not started |
| Formal development sample | N=0 |
| Final holdout | sealed and unconsumed |

Exit code 84 is emitted by the frozen runner's clean-worktree gate when `git status` fails or reports tracked changes. It occurs before either patch is applied and before the test command runs. The receipt deliberately stores bounded stderr hashes rather than raw stderr, so the narrower subcause cannot be proved without a selective rerun. The protocol forbids that rerun, and the controller correctly stopped.

## Exact conclusion boundary

This is a terminal qualification/execution failure, not a model result:

- The exact frozen cohort was not executable under the frozen qualification system.
- No v2 adapter exists from this run, and no base/v1/v2 model comparison occurred.
- None of the preregistered formal looks at `N=144`, `N=288`, or `N=432` was reached.
- This result neither proves nor disproves that trajectory fine-tuning would improve Nemotron Lightning.
- The 35-task Gibson Bench final holdout remains sealed.
- The original task must not be selectively repeated. A successor run requires an evaluator repair, equivalent preflight across every frozen image, and a newly frozen protocol before any new outcomes are collected.

## Cost and runtime

The durable experiment root was created at `2026-10-18T00:09:52Z`; the terminal receipt was recorded at `2026-10-18T03:18:02Z`. At the live rate of `$3.96/hour`, that 3.1361-hour evidence window cost an estimated `$12.42`, below the `$30/hour` cap. This excludes any instance runtime before the durable root existed. The instance remains running because stopping or deleting it requires fresh explicit confirmation, so charges continue after this cutoff.

## Repository and reproducibility status

- GitHub main at experiment start: `fdd362909ea90d8055781b19167f9d0273b8362e`.
- Reviewed installed source: `700e1596559b86df5ddfac2eef5dd1c70bab0abb`.
- Reviewed multiline-test-identifier source patch SHA-256: `d31cdf4be53fc9bb894d4feebb94623328c6fcc4997f7efb263c4ed3e05d33c0`.
- Installed source diff SHA-256: `f83b1db48197e7eb6fea6bfa5e6edbc3c461ba2d7d8f7aec6a5d1865f5579595`.
- Preparation controller SHA-256: `aaa7c777c2db35eff0ec97567309629094cf1bd24ea7984c1a4f9f421cac940e`.
- Preparation body SHA-256: `c0f90a05ab3e891e93205842e866608528bd8562ec71eb292ef48e0152f21754`.
- Qualification controller SHA-256: `df30fefa0b5983bb262567f171f3f5684e6df210759d4f884be804d20b0bec17`.
- Qualification journal SHA-256: `882fe3bad17a9890ef2a8034b381bbf61b944847fc9b79fc2ed7bd44b566d3ef`.
- Qualification journal head: `65dfff54b91464f8f1340357e40e4eba5db2609a643d587c9b1f91a8fdf69cd5`.
- Terminal receipt SHA-256: `063304b83ce4b5b36200f480e38164782d6fed3aa05277a4568b2e98bcdc01b2`.
- Final holdout: sealed and unconsumed.

The public-safe journal, terminal record, preparation hashes, limitations, cost record, and verification script are included in this package. Docker credentials, private configuration, image layers, model weights, and raw environment dumps are excluded.

The final canonical repository checks passed: `316 passed, 170 subtests passed` in the scoped pytest suite and `109 tests` in unittest discovery. The frozen evidence verifier and every entry in `SHA256SUMS` also passed.
