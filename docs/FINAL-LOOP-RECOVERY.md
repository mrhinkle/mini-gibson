# Mini-Gibson final-loop recovery checkpoint

Checkpoint refreshed at `2026-10-18T02:15:41Z`. This document separates completed, merged work from the GPU-dependent work currently executing.

## Current status

- GitHub `main` at the evidence cutoff: `fdd362909ea90d8055781b19167f9d0273b8362e`.
- Open pull requests: none.
- Experiment status: infrastructure and outcome-blind cohort freeze complete; authenticated preparation is 398/456; v2 qualification, training, and formal evaluation have not produced outcomes.
- Final 35-task Gibson Bench v0.1 holdout: sealed and unconsumed.
- Brev `weird-white-ocelot` (`ds7uiptfk`, 2xA100 80 GB) is running, healthy, and shell-ready at `$3.96/hour`; no Brev Connect nodes are listed.
- Docker authentication is valid, but the browser-authenticated account has no active subscription and Docker enforces a 200-pull hourly window. Do not purchase or change a subscription without Mark's explicit billing decision.
- The durable preparation controller is waiting and resuming without discarding its 398 cached records. The authenticated rolling qualification controller is armed behind the two preparation markers.
- Active GPU compute remains below the approved `$30/hour` total cap.

The current evidence/status report is [`docs/evidence/mini-gibson-final-loop-2026-10-18.md`](evidence/mini-gibson-final-loop-2026-10-18.md), with the machine-readable package under [`docs/evidence/mini-gibson-v2-2026-10-18/`](evidence/mini-gibson-v2-2026-10-18/README.md).

## Safety and claim boundary

- Never add tasks or change thresholds merely to obtain statistical significance.
- Do not open the final holdout until every preregistered development efficacy and safety gate passes.
- Do not stop or delete a Brev instance without fresh explicit confirmation from Mark.
- Do not create compute that exceeds the approved `$30/hour` total cap.
- Keep hosted Jev and Langfuse credentials out of scored runs. Local append-only receipts are authoritative.
- Do not post another Slack update unless Mark explicitly asks.
- Do not claim that v2 is trained, evaluated, significant, or promotable until the corresponding receipts are committed.

## Durable merged state

| Work | PR | Head | Merge |
| --- | ---: | --- | --- |
| Editable demo evidence fix | [#18](https://github.com/mrhinkle/mini-gibson/pull/18) | `e6380ea9782e939822e8314c28d1ddd2e77ed24f` | `7ad03e97f96b5d53fa6a1cd7a892743a738beb37` |
| Bounded sequential evaluation | [#26](https://github.com/mrhinkle/mini-gibson/pull/26) | `7c48c8be2e688367c67fbd5825cc45010f027e6e` | `d7d5eace68679c5dbd7ce82d48b1b621f2eb3308` |
| Hardened networkless evaluator | [#27](https://github.com/mrhinkle/mini-gibson/pull/27) | `05a35fba8cbc15efd681a8b8c76143c6f0bea5d1` | `3ff5dfdc37835b8db658e3f2e805e02b231be473` |
| Real outcome-blind cohort freeze | [#28](https://github.com/mrhinkle/mini-gibson/pull/28) | `29cff1ccfe25b073517382259dabf32ed6cd58f3` | `91b5c4aa110e5b5131061408c9508d372220f7ca` |
| Resumable qualification orchestrator | [#29](https://github.com/mrhinkle/mini-gibson/pull/29) | `d19bf65dc245b3b128afd9bec3d438b15bea4472` | `3a8f751dde5e9f7ff0e3f322f61b81ae6b93d374` |

The PR #29 exact tree passed the complete repository suite in an isolated environment: `281 passed`. Its independent Claude pre-push review returned `VERDICT: PASS`.

## Frozen source and cohorts

- Dataset: `nebius/SWE-rebench-V2`.
- Revision: `10483de0f50fe5da545942705a76c6150171af7f`.
- Parquet SHA-256: `0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`.
- Source rows: `32,079`; eligible before exclusions: `17,822`.
- Frozen sequence: `24` pilot tasks plus three formal cohorts of `144`, for `456` unique tasks and a maximum formal sample of `432`.
- All candidate IDs and issue, product-patch, test-patch, changed-file, and image-cluster fingerprints are cross-cohort disjoint.
- `sequential-plan.json` file SHA-256: `28c92eab536d2bd0cae6dc1596ae4fca245d7ba005caf15d355d6dc22cc3df9e`.
- `sequential-plan.json` canonical SHA-256: `961ee3c99b89248316f34dcbf8b30caa32291aebb5b239f8a2523634abbd6427`.
- `pre-plan-exclusions.json` file SHA-256: `5660348a58783a6e600db8b5864eec301fddc8c351d39061c8adffb13f01aad8`.
- `pre-plan-exclusions.json` canonical SHA-256: `e683db581e7db3a773793b08b1edb2e9fc769e15f43ea9e8cd8c0a9c3e47b454`.
- `freeze-evidence.json` SHA-256: `ca1ba1c045a883ef256ee74f45fe21d6a7d24e8962715275d6bb4fc847271210`.

A verified local dataset copy exists at:

`/Users/mrhinkle/Documents/Codex/2026-10-17/did/work/freeze-real-cohorts-20261017-local/pinned-swe-rebench-v2/10483de0f50fe5da545942705a76c6150171af7f/train-00000-of-00001.parquet`

## Frozen statistical design

- The 24-task pilot selects the 30-versus-50-turn budget only and is excluded from confirmatory inference and v2 training.
- Formal looks occur only at cumulative `N=144`, `288`, and `432`.
- Primary comparison: v2 versus base, paired task-level resolved outcome.
- Exact one-sided McNemar local alpha budgets: `0.01`, `0.015`, and `0.025`.
- Efficacy also requires at least `+5` percentage points observed absolute uplift.
- Frozen mathematical-impossibility and conditional-power futility rules apply at interim looks.
- Promotion additionally requires the conservative malformed-response safety gate and zero verified tampering, isolation, parser, or receipt failures.
- Stop at `N=432` if no success. Anything beyond that is a new experiment with fresh tasks and fresh alpha.

## Current scientific finding

The v1 adapter is not promotable. Across 48 fresh development issues it resolved `16/48`, compared with base `9/48`, an observed gain of `7` tasks or `14.58` percentage points. Paired outcomes were 12 tuned-only wins and 5 base-only wins; the one-sided exact paired p-value was `0.0717316`, above the frozen `0.05` boundary.

Tool reliability regressed materially: malformed responses affected `21/48` tuned tasks versus `8/48` base tasks. The one-sided paired degradation p-value was `0.000488`. The supported conclusion is: **promising issue-resolution signal, unsafe tool-format regression, no statistically established upgrade**.

## Active resume sequence

1. Allow the reviewed authenticated controller to finish the remaining 58 image-metadata records through the bounded registry window.
2. Verify the sealed 456-row material/parser/AST package, immutable image lock, and both completion markers.
3. Let the authenticated rolling controller qualify one frozen task at a time, preserving each receipt and stopping on the first terminal or safety failure.
4. Run `python -m evaluation.qualify_candidates --dry-run` and resolve every reported prerequisite without weakening a gate.
5. Qualify in bounded batches. Each task must produce two base-fail and two gold-pass receipts through the hardened networkless backend.
6. Finalize runnable cohort locks and the complete v2 training exclusion registry only after all 456 tasks qualify.
7. Select successful executable OpenHands/Scale-SWE trajectories outside the pilot, all 432 development tasks, and the final holdout. Keep SWE-smith auxiliary data at or below the frozen 10–20% cap.
8. Run a one-step v2 training smoke, then bounded resumable training with remote logs/checkpoints and completion markers.
9. Use the 24-task pilot to freeze the turn budget.
10. Evaluate base, v1, and v2 identically at the three formal development looks, applying efficacy, futility, and safety rules exactly.
11. Open the final holdout only if all development promotion gates pass.
12. Replace provisional demo findings with final verified results, render and inspect the video, obtain cross-vendor review, and merge through a new PR.

## Fast recovery checks

```bash
gh pr list --repo mrhinkle/mini-gibson --state open
gh api repos/mrhinkle/mini-gibson/commits/main --jq .sha
brev ls --json
brev ls nodes --json
git -C /Users/mrhinkle/Code/mini-gibson fetch origin --prune
```

Do not stop the running instance, change the Docker subscription, or create replacement compute without fresh explicit confirmation.
