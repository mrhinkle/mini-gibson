# Mini Gibson + Verifier + Jev: Design

Red Hat × NVIDIA Small Models Hack, Raleigh, Oct 17–18, 2026.
Base plan: https://gist.github.com/mrhinkle/7a84204fe287ce9a5809543da0df5b64

## The one rule

**Only the environment certifies completion.** Nothing in this design — not the adapter, not Jev, not any LLM judge — can mark a task done. The verifier's job is to *catch* false claims early, label failures, and send the agent back with specifics. The harness's own test rerun is the only thing that says "resolved."

## Architecture

```
            task
              │
              ▼
   ┌─────────────────────┐   tool calls    ┌──────────────┐
   │ Nemotron 3.5        │ ───────────────▶│  repo sandbox │
   │ Lightning (vLLM)    │ ◀─────────────── │  (Brev)       │
   │ + Mini Gibson LoRA  │   observations   └──────────────┘
   └─────────┬───────────┘
             │ "done"
             ▼
   ┌──────────────────────────────── VERIFIER ────────────────────────────────┐
   │ 1. Computational sensors (deterministic, verify.py)                      │
   │    • test files checksum unchanged (unless task allows)                  │
   │    • harness reruns the test command itself → exit code                  │
   │ 2. Inferential sensor: Jev (jev_sensor.py)                                │
   │    • Does the final message claim results the log doesn't show?           │
   │    • Was a failure ignored? Were tests weakened? Did tests actually run?  │
   │    → failure class + calibrated probability                               │
   │ 3. Policy (route()):                                                     │
   │    • env fails            → REJECT, send Jev's specifics back to agent   │
   │    • env passes, Jev clean → ACCEPT                                       │
   │    • env passes, Jev flags → ACCEPT but log "suspicious pass" for review  │
   │    • Jev uncertain (0.3–0.7) → human/review queue, never auto-label       │
   └───────────────────────────────────────────────────────────────────────────┘
```

Jev's three jobs, in order of value:

1. **Label the training data at scale.** Run Jev over the ~1,500 PR session logs to find premature-completion episodes (claimed done, evidence missing). High-confidence yes → negative examples for the adapter; high-confidence no + env-verified → positives; uncertain → Mark reviews a sample. Cheap, fast, calibrated, and keeps the auditor out of the same model family as the agent (research F5).
2. **Classify failures in the eval.** The gist's failure taxonomy (premature completion, wrong tool, ignored test failure, repair failure) gets an automatic first-pass label with a probability, instead of hand-labeling every run.
3. **Fast repair loop at runtime.** When the agent says "done" but Jev sees no test output in the log, bounce it back with that specific gap before the full verification run.

## Why Jev here and not a second fine-tune

The original "Option A" was training a small verifier model. Jev does that job without a second training run in a 14-hour hackathon, and its confidence values give us the confidence-line method from Mark's AI Lesson on Jev for free. The scope stays at **one** fine-tune (the Mini Gibson adapter).

## Evaluation (extends the gist)

Same frozen, time-split held-out tasks; four configurations:

| Config | What it isolates |
|---|---|
| Nemotron baseline | starting point |
| + Gibson harness (computational sensors only) | what deterministic governance buys |
| + harness + Jev sensor | what an inferential sensor adds (fewer false "done" loops, faster repair) |
| + harness + Jev + Mini Gibson adapter | what training adds on top |

Plus a **sensor eval** on the 98 documented incidents: Jev's precision/recall at detecting premature completion, and whether its misses cluster at low confidence (`eval_sensor.py`). If misses cluster below a confidence line, the routing policy is sound; if they don't, Jev stays a labeling aid only.

## Open risks — check before Oct 17

- **Hackathon rules.** Models are capped at 33B, and Jev is an external API whose size we don't know. Confirm with organizers that an auxiliary API sensor is allowed. Fallback: swap `JevSensor` for a small open judge served on vLLM (the interface is the same).
- **Gibson's own G5 gate.** A metered external API is a human-gated spend under AGENTS.md. Mark approves it explicitly.
- **Input size.** The docs don't state a max state size. Truncate logs to the final N tool calls plus all test outputs; measure tokens.
- **Vendor claims.** Speed, cost, and calibration numbers are TypeSafe's own. Our sensor eval is the check.
- **Nemotron 3.5 Lightning 30B-A3B LoRA on Brev.** Confirm GPU memory and that the training stack supports this MoE architecture.

## Prior art: JevCI (and how we're different)

[JevCI](https://github.com/sumant1122/jevci) (Sumant Sogikar, Sept 2026; reviewed in `research/repos/jevci.md`) already puts Jev into CI. It scores a **diff** on four dimensions: commit message quality, alignment between docs and code, API breaking risk, and a yes/no secrets audit. It uses a pass threshold (default 70) and runs as a CLI, a git hook, or a GitHub Action.

How Mini Gibson differs: JevCI judges **the code change**. We judge **the agent's claim about the change**, checking whether "done, tests pass" is backed by evidence in the run log. The two are complementary. In the pitch: "JevCI asks whether the diff is good. Gibson asks whether the agent is telling the truth."

What we borrow:
- **`TYPESAFE_API_KEY`** as the env var name, which matches JevCI and keeps setup familiar.
- **A secrets audit as a data-prep step.** Before any trajectory goes into training or the published adapter, run a yes/no secrets check *and* a regex scanner (e.g. gitleaks) over it. Use both, because a probability is not a guarantee, and JevCI's own write-up calling typed output "deterministic" overstates it.
- **Optional stretch:** run JevCI's diff lenses alongside our claim sensor as a fourth verifier signal.
