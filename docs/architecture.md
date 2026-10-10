# Architecture

```
             EXPERIMENT MANIFEST
                    |
        +-----------+-----------+
        |           |           |
      MODEL       AGENT     ENVIRONMENT
        |           |           |
        +-----------+-----------+
                    |
                   TASK
                    |
                   RUN
                    |
                 EVIDENCE
                    |
                  SCORE
```

**Model** — reasoning/generation artifact.

**Agent** — runtime converting observations/model outputs into actions.

**GibsonEnv** — task state, declared tool authority, observations, repair budget, deterministic evidence, verification, terminal state.

**Task** — frozen problem and repository state with no hidden-answer exposure.

**Experiment runner** — validates manifests, isolates runs, applies budgets, records provenance, resumes infrastructure failures, scores trials, produces reports.

An agent may request completion. It may not award `VERIFIED`.

## Optional decision service

[Optional Jev](jev.md) sits beside the operational control plane. `DecisionService` calls the fixed official TypeSafe endpoint with bounded metadata and versioned choice/noul/score questions, then emits a separate decision receipt. It cannot generate code, substitute the coding model, alter Evidence Gate logic, award `VERIFIED`, change tool permissions, choose adapter promotion, or change trial scores.

The current `GibsonEnv(..., decisions=service)` connection records tool-risk advice before existing permission checks and leaves tool execution/verification authority intact. Supervisor/routing and anomaly APIs are available as hooks; the foundation does not yet provide those runners. Enabled Jev requires telemetry; failures and low confidence yield deterministic conservative/human advice.

The manifest extension treats missing scoring context as scored. Remote calls are excluded by default; identical-policy scored mode requires a complete declared comparison, explicit arm identity and frozen policy hash. Routing stays outside scored execution in all modes. Shared hook placement, state projection and immutable result/report boundaries are integration responsibilities.
