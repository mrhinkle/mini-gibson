# Mini-Gibson final-loop recovery checkpoint

Checkpointed at `2026-10-17T21:42:30Z` so the laptop can be shut down without losing the experiment state.

## Safety and scope

- The 35-task Gibson Bench v0.1 final holdout remains sealed. Do not run it until the preregistered development gates pass.
- Do not stop or delete any Brev instance without fresh explicit confirmation from Mark.
- Keep total compute at or below the approved `$30/hour` cap. Do not create another instance until current hourly prices have been verified.
- Keep hosted Jev and Langfuse credentials out of scored runs. Local append-only evidence is authoritative.
- Do not post another Slack update unless Mark explicitly asks.

## Durable GitHub state

- `origin/main`: `23b4c28a25a2bd1cff03b9c39ce2ec4bb3d6a24d`
- Merged evidence/lifecycle PR #21: head `befe81539d99c98bb2e7ee05e147487874368dc2`, merge `f378f215982e5b3dc36620c74bb6f82a09da71c8`
- Merged real-repository cohort tooling PR #24: head `d72d1c15b7e8cf0fc80fb96d088ca699dc53c783`, merge `23b4c28a25a2bd1cff03b9c39ce2ec4bb3d6a24d`
- Editable demo PR #18 remains open at `af68f70efb6687ae28ec47dae301bd5f1701d772`; do not merge it until the evidence-hash review finding is fixed and cross-vendor review passes.
- The combined demo MP4 is already merged by PR #23 under `presentation/combined-demo/`.

## Durable adapter archive

- Brev: `/ephemeral/mini-gibson-lightning/exports/mini-gibson-lightning-20261017.tgz`
- Laptop copy: `/Users/mrhinkle/Documents/Codex/2026-10-17/did/work/lightning-artifacts/mini-gibson-lightning-20261017.tgz`
- Archive SHA-256: `75881702a163aa163cc3cfc7270c298bc1c4b0e84587b8fb2348d84c1a42c7ef`
- Path-list SHA-256: `cf5ea3b6de49934d523f8272a1a67c85b8f891bd4f17962d4c78c81d0d0112ed`
- Restored-copy offline adapter reload smoke: PASS.

## Brev instances at checkpoint

| Name | ID | Machine | State |
| --- | --- | --- | --- |
| `mini-gibson-lightning-ft` | `3f81y01fz` | `hyperstack_H100x2` | running, healthy/ready |
| `weird-white-ocelot` | `ds7uiptfk` | `a100-80gb.2x` | running, healthy/ready |
| `mini-gibson-ocr7b-lora` | `c23h8vmme` | `massedcompute_H100` | running, healthy/ready |

The known Lightning price is `$6/hour`. Verify the other two current prices before scheduling parallel GPU work so the combined rate remains within the cap.

## Work in progress

- Backend branch: `codex/rebench-docker-backend-20261017`
- Backend worktree: `/Users/mrhinkle/Documents/Codex/2026-10-17/did/work/mini-gibson-rebench-backend`
- Cohort branch: `codex/rebench-cohort-freeze-20261017`
- Cohort worktree: `/Users/mrhinkle/Documents/Codex/2026-10-17/did/work/mini-gibson-rebench-cohort`
- Recovery branch: `codex/final-loop-recovery-20261017`
- Demo source worktree: `/Users/mrhinkle/Code/mini-gibson-wt/demo-progress-20261017`

Local agents pause when the laptop is off. On recovery, inspect each worktree before restarting or replacing its task. Never run two agents in one worktree.

## Resume sequence

1. Refresh `origin/main`, GitHub PR state, Brev instance state, GPU health, disk capacity, and current hourly prices.
2. Inspect the backend worktree and recover the Docker-backed networkless evaluator implementation. Run its focused tests and independent cross-vendor review.
3. Finish and freeze the disjoint 24-task pilot plus 144-task development cohort from SWE-rebench V2 revision `10483de0f50fe5da545942705a76c6150171af7f`.
4. Freeze the training/evaluation exclusion registry before selecting v2 rows. Split by repository and image/task cluster, not only instance ID.
5. Run qualification twice: base must fail the declared fail-to-pass set, and the gold patch must pass fail-to-pass plus pass-to-pass. Store image digests and receipts.
6. Use only the 24-task pilot to freeze the 30-versus-50-turn budget.
7. Build the v2 mixture from successful executable OpenHands trajectories, Scale-SWE-Distilled, and at most 10–20% SWE-smith auxiliary data after exclusions.
8. Run a one-step training smoke, then the bounded v2 fine-tune. Persist logs, checkpoints, manifests, hashes, and state under the remote final-loop root below.
9. Evaluate base, v1, and v2 on all 144 development tasks with identical locked settings and the hardened networkless verifier.
10. Apply the preregistered promotion gates. Run the 35 final holdouts only if the development gates pass.
11. Fix PR #18 evidence hashing, replace provisional claims with the final verified findings, render and inspect the video, obtain cross-vendor review, then merge.

## Remote final-loop root

Use this durable Brev path for resumable state:

`/ephemeral/mini-gibson-lightning/final-loop-20261017/`

The machine-readable checkpoint is `RECOVERY.json`, SHA-256 `2a5ce9a8daad123edefc9bc3c5579c0cac727e335e01f3317ced2de8655ad803`. The laptop and Brev copies matched at checkpoint time.

Every remote stage must write append-only JSONL or atomic JSON state, immutable hashes, the exact Git SHA, and a completion marker. Long-running jobs must run in a persistent remote process (`tmux`, `systemd-run`, or equivalent), not an SSH session tied to the laptop.

## Fast recovery checks

```bash
gh pr list --repo mrhinkle/mini-gibson --state open
gh pr view 18 --repo mrhinkle/mini-gibson --json state,headRefOid,reviewDecision,statusCheckRollup
brev ls
git -C /Users/mrhinkle/Code/mini-gibson fetch origin --prune
git -C /Users/mrhinkle/Code/mini-gibson worktree list --porcelain
```

Then verify the remote checkpoint:

```bash
brev exec mini-gibson-lightning-ft -- bash -lc 'cat /ephemeral/mini-gibson-lightning/final-loop-20261017/RECOVERY.json'
```

## Current scientific result

The v1 adapter is not promotable. Across 48 development tasks it resolved `16/48` versus base `9/48` (`+14.58` percentage points), but the one-sided exact McNemar result was `p=0.0717316`, and malformed-response task incidence worsened materially (`21/48` tuned versus `8/48` base; one-sided sign `p=0.000488`). The next valid step is the larger real-repository development evaluation and a v2 data mixture, not use of the sealed final holdout.
