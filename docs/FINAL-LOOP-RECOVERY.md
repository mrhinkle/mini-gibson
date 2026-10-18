# Mini-Gibson final-loop recovery checkpoint

Checkpoint refreshed at `2026-10-18T03:18:02Z`. This document records the terminal boundary of the frozen v2 experiment.

## Current status

- GitHub `main` at the evidence cutoff: `fdd362909ea90d8055781b19167f9d0273b8362e`.
- Findings pull request: [#31](https://github.com/mrhinkle/mini-gibson/pull/31).
- Experiment status: authenticated preparation completed 456/456; the first frozen qualification receipt was terminal and unqualified; v2 training and formal evaluation did not start.
- Final 35-task Gibson Bench v0.1 holdout: sealed and unconsumed.
- Brev `weird-white-ocelot` (`ds7uiptfk`, 2xA100 80 GB) is running, healthy, and shell-ready at `$3.96/hour`; no Brev Connect nodes are listed.
- Docker authentication and bounded retries completed preparation without discarding cached records. No subscription or billing change was made.
- Terminal receipt: `natcap__invest-1365`, ordinal 1, receipt SHA-256 `063304b83ce4b5b36200f480e38164782d6fed3aa05277a4568b2e98bcdc01b2`. All four repeats returned 84 at the clean-worktree precondition and lacked the integrity marker.
- Active GPU compute remains below the approved `$30/hour` total cap.

The current evidence/status report is [`docs/evidence/mini-gibson-final-loop-2026-10-18.md`](evidence/mini-gibson-final-loop-2026-10-18.md), with the machine-readable package under [`docs/evidence/mini-gibson-v2-2026-10-18/`](evidence/mini-gibson-v2-2026-10-18/README.md).

## Safety and claim boundary

- Never add tasks or change thresholds merely to obtain statistical significance.
- Do not open the final holdout until every preregistered development efficacy and safety gate passes.
- Do not stop or delete a Brev instance without fresh explicit confirmation from Mark.
- Do not create compute that exceeds the approved `$30/hour` total cap.
- Keep hosted Jev and Langfuse credentials out of scored runs. Local append-only receipts are authoritative.
- Do not post another Slack update unless Mark explicitly asks.
- Do not rerun, replace, or selectively repeat the terminal frozen task. This experiment is closed before training.
- Do not claim that v2 is trained, evaluated, significant, or promotable; no v2 model outcome exists.

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

## Terminal boundary and safe successor

1. Preserve the sealed preparation hashes, terminal journal, receipt, and remote recovery manifest.
2. Publish the exact finding through PR #31: the frozen cohort failed executability before training, so v2 remains unadjudicated.
3. Leave the final holdout sealed and do not reuse the terminal task inside this experiment.
4. For a successor experiment, repair the clean-worktree ownership/state boundary and preflight every frozen image under the same unprivileged runtime.
5. Freeze a new protocol and cohort before collecting any new qualification or model outcomes.
6. Only after that new cohort fully qualifies may v2 training, pilot budget selection, and formal base/v1/v2 evaluation resume.

## Fast recovery checks

```bash
gh pr list --repo mrhinkle/mini-gibson --state open
gh api repos/mrhinkle/mini-gibson/commits/main --jq .sha
brev ls --json
brev ls nodes --json
git -C /Users/mrhinkle/Code/mini-gibson fetch origin --prune
```

Do not stop the running instance, change the Docker subscription, or create replacement compute without fresh explicit confirmation. The terminal package estimates `$12.42` through the receipt cutoff; charges continue while the instance remains running.
