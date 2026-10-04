# GibsonEnv

Common environment contract for evaluation, demo, and possible future outcome-based training.

```
reset(task) -> observation
step(action) -> observation, done
verify() -> verification
```

The environment owns declared tool authority, evidence, repair budget, verification, and terminal state. The model/agent cannot self-award VERIFIED.

Reward decomposition is experimental and separate from benchmark scoring. RL is post-hackathon unless the design-freeze review explicitly changes scope.
