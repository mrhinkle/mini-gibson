# Jev integration

Mini Gibson can optionally call TypeSafe Jev as a bounded decision service.

## Supported decision points

- supervisor action: continue / retry infrastructure / stop / human escalation;
- tool-risk classification;
- benchmark anomaly triage.

Jev is **disabled by default**.

## Configuration

```bash
export MINI_GIBSON_JEV_ENABLED=true
export TYPESAFE_API_KEY=...
export MINI_GIBSON_JEV_MODEL=jev-latest
export MINI_GIBSON_JEV_MIN_CONFIDENCE=0.80
```

The API key must never be committed.

## Safety and experiment boundaries

Jev must never:
- generate code;
- replace Nemotron;
- award `VERIFIED`;
- override the deterministic Evidence Gate;
- silently change tool permissions;
- decide LoRA promotion;
- inspect hidden benchmark answers;
- retry failed tasks until they pass.

For causal A/B/C experiments, Jev is either outside the scored loop or configured identically across every compared arm.

Every Jev request records a stable state/question hash, question-set version, returned typed answers, model, latency, confidence when exposed by the API, and fallback/error state.

Low-confidence or unavailable decisions fall back to a deterministic safe action.
