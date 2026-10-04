# Historical Learning / LoRA Plan

## Goal

Teach engineering-agent behavior, not Gibson source-code memorization.

## Source episode

Issue/contract → observed attempt → tests/review evidence → failure → explicit diagnosis where available → repair → regression proof → verification → outcome.

Never invent hidden chain-of-thought.

## Dataset quality

Prefer explicit contracts, exact SHAs, real failures/reviews, attributable repairs, deterministic tests, terminal evidence, and accepted outcomes.

Represent residual defects/follow-up PRs honestly as chains.

## Initial target

- 25+ scored candidates;
- 10+ gold trajectories before first training;
- expand only when provenance quality remains high.

## Training

Default candidate: BF16 Nemotron 3.5 Lightning + LoRA PEFT using NVIDIA's verified path.

Training is blocked until benchmark freeze and A/B baseline capture.

## Promotion

Evaluate base+B vs adapter+C on untouched temporal and external holdouts.

Promote adapter only if pre-registered metrics improve without material task-resolution degradation.

If not, ship base Nemotron + Gibson and report the negative learning result.
