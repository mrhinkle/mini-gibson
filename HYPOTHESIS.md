# Hypotheses

## Primary

A small open model becomes measurably more reliable at autonomous software engineering when it operates inside an evidence-driven engineering environment, and can improve further when specialized on high-quality historical engineering trajectories.

## H1 — Harness effect

Holding model, tasks, tool contract, compute budget, and trial policy constant as tightly as the frozen protocol permits, Gibson increases **verified task resolution rate** relative to the fair baseline.

**Null:** no material improvement.

## H2 — Historical-learning effect

Holding GibsonEnv and evaluation constant, a Nemotron adapter trained on leakage-controlled Gibson historical trajectories improves held-out verified task resolution or pre-registered reliability metrics.

**Null:** no improvement, or degradation sufficient to reject adapter promotion.

## H3 — Runtime sensitivity

Cross-agent claims are made only for runtimes satisfying Agent Adapter Conformance. Hermes, Claude Code, Codex, and Grok are not assumed equivalent.

## Falsification

Report honestly if gains disappear on external holdouts or are explained by extra compute, retries, tools, context, leakage, or a stronger runtime.
