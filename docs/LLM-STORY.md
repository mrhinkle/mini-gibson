# The LLM story, in plain language

**Team: Merge-Geezers · Project: Mini Gibson**

Mini Gibson asks whether a smaller open language model can help with the
slowest part of AI-assisted coding: getting from a plausible edit to a change
a human can trust. Our deliverable is the **repeatable training and evaluation
pipeline**, not a claim that the present adapter is ready to ship.

## The cast

| Part | Its job in this experiment |
| --- | --- |
| [NVIDIA Nemotron 3.5 Lightning 30B-A3B](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) | The coding model. It reads an issue, chooses tools, proposes changes, and responds to feedback. We pinned revision `a9904d24bcc1d289a1950fa9d2b978c47cf903b9`. |
| [OpenHands trajectories](https://huggingface.co/datasets/nvidia/SWE-Hero-openhands-trajectories) | Examples of real agent behavior, including the sequence of actions and outcomes. The completed fine-tune directly used the pinned SWE-Hero source revision `150bc119e52c647216fce285fd801f16b6fd745b`. |
| [NeMo AutoModel](https://github.com/NVIDIA-NeMo/Automodel) | The LoRA training framework. It changed a small adapter rather than publishing a new full model. |
| GibsonEnv and the locked evaluator | The independent referee. They constrain tools and budgets, run verification, record receipts, and prevent the model from declaring itself successful. |
| [NeMo Gym](../integrations/nemo_gym/README.md) | A **working local, non-scored feasibility fixture** for checking tool-call format; not used for the completed fine-tune or scored evaluation. |

## What actually happened

We filtered the historical source into **188 training examples and 30
development examples**, preserving exact tool rendering. A bounded LoRA run
completed **94 of 94 optimizer steps**. The adapter passed an offline reload
check. These are training and artifact checks; they are not proof of better
coding behavior.

We then gave the base model and tuned adapter the same 48 fresh development
issues under the same frozen prompts, tools, turn budget, decoding, and
networkless verifier. The tuned model resolved **16/48**, versus **9/48** for
the base model: an observed **+14.58 percentage points**. The one-sided exact
paired test was `p=0.0717316`, above the preset boundary. Moreover, malformed
responses affected **21/48** tuned tasks versus **8/48** base tasks
(`p=0.000488`). The result is a promising directional resolution signal **and
a clear reliability regression**. We did not promote the adapter or spend the
35-task final holdout.

The later v2 run stopped before model evaluation because its frozen
qualification gate failed on the first task. The successor R3 run was a
456-task **evaluator-compatibility preflight**, not a model comparison: 406
packages were compatible and 50 were not, so it stopped before more training
or model evaluation. It ran no agent or LLM. Neither the v2 stop nor R3 can be
counted as a new Nemotron result. See the
[completed v1 evidence](evidence/lightning-openhands-2026-10-17/REPORT.md),
[v2 stop report](evidence/mini-gibson-v2-2026-10-18/REPORT.md), and
[successor report and full matrix](evidence/mini-gibson-successor-2026-10-18/REPORT.md).

## Why NeMo Gym is in the story

The first adapter's extra malformed calls tell us that learning to finish a
coding task and learning to speak the tool protocol are different skills.
On October 18 we ran the pinned NeMo Gym v0.7.0 upstream verifier/session
example (**5 passed**) and a Mini Gibson-specific synthetic verifier fixture
(**1 passed**, with four cases). The latter checks JSON and patch-call framing
and rejects self-awarded completion. It calls no model, executes no patch, and
does not replace our scored evaluator. [Commands, source pin, and limitations
are in the integration receipt](../integrations/nemo_gym/README.md).

The next scientific step is not to declare victory from that smoke test. It
is to repair compatibility for an entire newly frozen cohort, train on more
diverse contamination-screened successful trajectories, and compare base and
tuned Nemotron again under identical rules. Gym could help collect and inspect
those future tool-use rollouts; an actual issue reward must come from a
hash-bound GibsonEnv verification receipt. We will only claim improvement if
the preregistered issue-resolution **and** reliability gates pass.
