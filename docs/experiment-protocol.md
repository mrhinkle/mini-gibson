# Experiment Protocol — DRAFT / DESIGN FREEZE PENDING

This document defines the decisions that #417 must freeze.

## Questions

### H1 Harness effect
Does Gibson increase verified task resolution relative to a fair baseline?

### H2 Historical-learning effect
Does historical specialization improve held-out reliability with GibsonEnv held constant?

### H3 Runtime sensitivity
How sensitive are results to the agent runtime, and which runtimes satisfy controlled-comparison conformance?

## Minimum experimental arms

- **A — Fair baseline:** base Nemotron + frozen comparable agent/tool protocol.
- **B — Gibson:** same model + same task/tool/compute/trial constraints + Gibson engineering mechanisms.
- **C — Historical Mini Gibson:** specialized adapter + same B environment.

Exact ablations remain UNFROZEN pending #417.

## Controls to freeze

- model revision;
- inference parameters;
- hardware or normalized compute policy;
- task input;
- tool schemas/permissions;
- max steps;
- repair/retry policy;
- token/context budget;
- wall-clock budget;
- number of trials;
- scoring.

## Retry rule

Infrastructure failure may be retried under a pre-registered policy and is labeled.

Engineering/model failure is a scored trial outcome. Never rerun a failed task until a lucky sample passes and report only the pass.

## Holdouts

1. development/tuning;
2. validation;
3. temporal Gibson holdout;
4. external unrelated-repository holdout.

Final holdouts are not used for prompt, harness, reward, dataset, or LoRA decisions.

## Primary metric

Verified task resolution rate.

## Secondary metrics

- valid tool-call rate;
- wrong-tool rate;
- invalid-argument rate;
- recovery rate;
- repair success;
- premature-completion rate;
- verifier rejection;
- tool calls/success;
- tokens/success;
- elapsed time/success.

## Statistical reporting

Report all trials, denominators, mean/median where appropriate, and uncertainty suitable to sample size. Avoid significance theater with a tiny benchmark. Exact method freezes with benchmark size.
