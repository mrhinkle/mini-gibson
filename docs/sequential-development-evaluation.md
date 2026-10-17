# Bounded sequential SWE-rebench V2 development protocol

Status: preregistration tooling, 2026-10-17. This protocol does **not** open or
run the sealed 35-task Gibson Bench v0.1 final holdout.

## Why the loop is bounded

“Keep testing until significant” is not a valid experiment rule: repeatedly
examining results and adding tasks at will raises the false-positive rate. Mini
Gibson instead freezes one budget-only pilot and three scored cohorts before it
looks at scored outcomes or chooses v2 training rows. The three cumulative looks
spend one-sided alpha `0.010`, `0.015`, and `0.025`; the sum is `0.050`, so a
Bonferroni argument controls the familywise false-positive rate even though the
looks are correlated.

The maximum is 432 scored development tasks. A fourth development cohort is
forbidden. The final 35-task holdout must not be opened merely because the
development sequence did not reach `p < 0.05`.

## Freeze order

Use `nebius/SWE-rebench-V2` split `train` at exact revision
`10483de0f50fe5da545942705a76c6150171af7f`.

Before scored outcomes or v2 training-row selection:

1. Build the private base exclusion registry from the sealed final holdout,
   prior development fixtures and all already-used training material. Only
   identities and fingerprints enter the registry; holdout task bytes stay
   sealed.
2. In one deterministic call, freeze these mutually disjoint candidate reports:

   | Cohort | Tasks | Purpose | Cumulative scored N | One-sided alpha |
   | --- | ---: | --- | ---: | ---: |
   | `pilot-budget` | 24 | select 30 or 50 turns only | 0 | 0 |
   | `development-a` | 144 | primary look 1 | 144 | 0.010 |
   | `development-b` | 144 | primary look 2 | 288 | 0.015 |
   | `development-c` | 144 | primary look 3 | 432 | 0.025 |

3. Qualify every selected task twice: the pristine base commit must fail the
   declared fail-to-pass checks twice, and the gold patch plus sealed test patch
   must pass all fail-to-pass and pass-to-pass checks twice. Candidate reports
   remain non-runnable until image digests, AST fingerprints and receipt hashes
   are present in qualified locks.

The candidate plan hashes the exact private base exclusion registry, so a later
registry substitution fails finalization even when it would happen to select the
same task IDs.
4. Finalize the training exclusion registry from all four qualified locks.
   Successful finalization proves that all 456 task IDs, repositories, source
   PRs/issues, base and merge commits, image clusters, patch/test-patch hashes,
   normalized issue hashes, changed-file hashes and AST-edit hashes are excluded
   before any v2 training trajectory is selected. If any lock is missing or
   disagrees with its candidate manifest, training selection is blocked.
5. Persist a pre-outcome execution-freeze manifest that hashes all four
   qualified locks, the complete training exclusion registry, and the ordered
   456-task and 432-development-task ID lists. Formal outcomes are invalid unless
   they bind this manifest. This ensures order, exclusions and executable lock
   hashes are frozen before the first formal outcome.
6. Use only the 24-task pilot to freeze the common 30- or 50-turn budget. The
   pilot supplies no efficacy claim and is never pooled into scored outcomes.

Generate the four candidate manifests with:

```bash
python -m evaluation.sequential freeze \
  --records /path/to/pinned-swe-rebench-v2.jsonl \
  --registry /path/to/pre-plan-exclusions.json \
  --plan-id mini-gibson-v2-sequential-2026-10-17 \
  --master-seed 414 \
  --output /path/to/sequential-plan.json
```

`evaluation/sequential.py` checks the plan again before hashing or assessment.
The plan schema and outcome schema are under `evaluation/schemas/`. Candidate
reports contain no problem statements, gold patches, test patches or declared
test IDs, and they are not executable cohort locks.

## Primary inference

The sole alpha-bearing comparison is paired task-level `resolved` for `v2`
versus `base`. At each cumulative look:

- compute `v2_wins`: base unresolved and v2 resolved;
- compute `base_wins`: base resolved and v2 unresolved;
- use the exact one-sided McNemar tail
  `P[Binomial(v2_wins + base_wins, 0.5) >= v2_wins]`;
- require the p-value to be at or below that look’s allocated alpha; and
- independently require an absolute resolution-rate uplift of at least five
  percentage points.

Both conditions must hold. `v1` is reported descriptively and receives no alpha
claim. This prevents the earlier adapter from becoming an unplanned second
primary comparison. The local thresholds are weighted Bonferroni budgets with
weights `0.20`, `0.30`, and `0.50`. Report the sequential adjusted p-value
through look `k` as `min(1, p1/0.20, p2/0.30, p3/0.50)`, using only p-values
available through that look.

## Safety and malformed-response non-inferiority

Any tamper detection or policy violation in any arm is a terminal safety failure.
It cannot be averaged away or repaired by collecting more tasks.

The v2 malformed-response gate uses paired discordances. Let `U` be tasks where
v2 is malformed and base is not, and `V` tasks where base is malformed and v2
is not. Treat `U/N` and `V/N` as the two marginal probabilities of mutually
exclusive multinomial cells. Compute a one-sided 97.5% exact Clopper-Pearson
upper bound for `p_U` and a one-sided 97.5% exact Clopper-Pearson lower bound for
`p_V`. Their difference, `RD_UCB = U_U - L_V`, has simultaneous coverage of at
least 95% by the Bonferroni split, regardless of the dependence between the two
paired cells. Promotion requires `RD_UCB <= 0.05`.

This conservative exact construction correctly allows `U=V=0` to establish
non-inferiority once N is large enough; it does not require the base model to
produce malformed responses. The report also includes observed malformed excess
`(U - V) / N`, but that point estimate is not the non-inferiority test.

At interim looks N=144 and N=288, stop for evidence of harm when malformed
excess is at least five points and the one-sided exact degradation McNemar
p-value `P[Binomial(U + V, 0.5) >= U]` is at most `0.005`.

This safety test is separate from the primary alpha spending. A primary efficacy
crossing with a safety failure is still a failure.

## Futility and stopping

At looks 1 and 2, stop for nonbinding futility if either rule holds:

- mathematical impossibility: `W - L + (432 - N) < 22`, so even v2 winning
  every remaining task cannot reach the required five-point uplift at N=432;
- exact conditional power under the fixed alternative is below `0.10`. The
  alternative freezes `delta*=0.08`, discordance `s*=0.35`, and future per-task
  multinomial probabilities v2-only win `0.215`, base-only win `0.135`, tie
  `0.650`. Conditional power is the probability of crossing either remaining
  local alpha/effect gate, stopping at the first crossing.

Futility cannot inflate type-I error because it only removes a future chance to
reject. It is formally nonbinding, but any operational override must be reported
as a protocol deviation; the alpha thresholds and maximum N do not change.

Otherwise:

- stop at the first look that meets primary efficacy **and** every safety gate;
- continue only to the next already-frozen cohort when the current look is
  neither terminal nor futile;
- stop immediately on a tamper/policy/integrity event or the preregistered
  interim malformed-harm boundary; withhold promotion when malformed
  non-inferiority is not established;
- stop without promotion after look 3 if efficacy is not met.

The development decision `stop_promote_to_final_holdout_decision` does not open
the final holdout automatically. It means the preregistered development gate has
passed and the separate final-holdout authorization boundary may be considered.

Assess a cumulative receipt with:

```bash
python -m evaluation.sequential assess \
  --plan /path/to/sequential-plan.json \
  --execution-freeze /path/to/execution-freeze.json \
  --outcomes /path/to/cumulative-look.json \
  --output /path/to/cumulative-assessment.json
```

The outcome file must bind the canonical plan and execution-freeze SHA-256s,
contain exactly the frozen prefix (144, 288 or 432 tasks), and include boolean
resolved, malformed, policy, tamper, isolation and receipt-consistency fields
for base, v1 and v2. Missing, duplicate, future or unplanned task IDs fail
closed.

## Findings table

The final report should carry one row per look with these fields so readers can
audit the stopping decision without reconstructing receipts:

| Field group | Required columns |
| --- | --- |
| Provenance | plan SHA, execution-freeze SHA, look, N, cohort IDs, model/adapter/config hashes |
| Resolution | base/v1/v2 resolved counts, `W`, `L`, `D`, observed delta, local p, local alpha, Bonferroni weight, sequential adjusted p |
| Malformed safety | base/v2 malformed counts, `U`, `V`, malformed excess, exact `RD_UCB`, five-point NI margin, interim degradation p |
| Integrity | tamper, policy, isolation and receipt-inconsistency counts by arm |
| Futility | impossibility flag, fixed-alternative conditional power, override/deviation flag |
| Decision | continue, efficacy stop, safety stop, futility stop or maximum-N no-promotion |

## Evidence boundary

Commit the frozen plan and its SHA-256 before training-row selection or scored
execution. For every qualification, training and scored run, preserve immutable
image/model/adapter/config hashes, append-only receipts and remote completion
markers. Do not edit the frozen plan after results exist; a required design
change creates a new experiment, not an in-place correction.
