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

## Brev training environment

Our hackathon training environment is an NVIDIA H100 (80 GB) instance on Brev.
The [October 17 environment evidence](docs/evidence/brev-h100-2026-10-17.md)
preserves the team-supplied console screenshot and the hardware shown there.
At capture, the instance was **Building** and the environment was **Waiting**;
completed training and model results require separate run receipts.

![NVIDIA Brev console showing the H100 80 GB instance during initialization](docs/evidence/assets/brev-h100-2026-10-17.png)

## Principles

- The model cannot award itself `VERIFIED`.
- Failed engineering attempts are evidence.
- Infrastructure retries and task retries are different.
- Holdouts stay untouched by prompt, harness, reward, and training decisions.
- Negative results are valid.
- Reproducibility is a deliverable.

Private preparation repo: do not publish holdouts, private historical data, secrets, or training artifacts without an explicit release decision.

## Optional Jev advice

The optional [Jev decision service](docs/jev.md) uses TypeSafe's official typed-decision API, is disabled by default, and never replaces Nemotron or GibsonEnv's completion authority. The implemented tool-risk hook records advice without changing permissions. Supervisor/routing and anomaly hooks are exported for future runner integration. Scored runs exclude remote Jev calls by default; an alternative mode validates a frozen policy identical across every declared arm.

Mark/Codex owns the adapter/configuration, fairness checks, telemetry and runtime tests; John/Grok owns future post-outcome anomaly/report consumption; Claude independently reviews and coordinates shared contracts. The Jev extension does not waive the pending design freeze.

Install with Python >=3.11 (`python -m pip install -e .`) and run `python -m unittest discover -v`. Tests use deterministic API fixtures; no live TypeSafe credential setup or API verification is included.

## Agent handoff (#433 observational baseline)

**Agents: start at [`docs/433-agent-kit/README.md`](docs/433-agent-kit/README.md).**

That kit has the workplan, copy-paste prompts (Codex + Claude computer use), Mark/John oversight checklist, portable runners, fixtures, schema, and a sample of real traces.

Related:

- Kickoff notes: [`docs/433-nemotron-baseline-kickoff.md`](docs/433-nemotron-baseline-kickoff.md)
- Canonical issue: https://github.com/The-AIE/the-gibson/issues/433
- Data layout: [`training/dataset/observational/`](training/dataset/observational/)

## License

See [LICENSE](LICENSE).
