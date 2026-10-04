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
