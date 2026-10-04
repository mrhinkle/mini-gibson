# Mini Gibson

**Small Model. Serious Engineer.**

Private preparation repository for the NVIDIA × Red Hat Small Models Hack, October 17–18, 2026.

## Question

> Can a small open model become measurably more reliable at autonomous software engineering when it operates inside an evidence-driven engineering environment—and improve further by learning from real historical engineering trajectories?

## Experiment

```
MODEL + AGENT + ENVIRONMENT + TASK = RUN → EVIDENCE → SCORE
```

Reference model: NVIDIA Nemotron 3.5 Lightning. Reference agent candidate: Hermes. Agents are substitutable only after passing a frozen conformance contract. GibsonEnv owns declared tools, evidence, verification, and completion authority.

Planned comparison:

1. **Baseline** — base Nemotron under a frozen minimal comparable agent/tool protocol.
2. **Harness** — same model with Gibson's evidence-driven engineering environment.
3. **Historical learning** — specialized Mini Gibson model with the same environment.

The causal protocol is not frozen until the Claude-led Kimi K3 + GLM-5.2 steelman review is complete.

## Principles

- The model cannot award itself `VERIFIED`.
- Failed engineering attempts are evidence.
- Infrastructure retries and task retries are different.
- Holdouts stay untouched by prompt, harness, reward, and training decisions.
- Negative results are valid.
- Reproducibility is a deliverable.

Private preparation repo: do not publish holdouts, private historical data, secrets, or training artifacts without an explicit release decision.
