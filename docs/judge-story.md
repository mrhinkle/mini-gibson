# Judge Story

*Team: Merge-Geezers · Project: Mini Gibson*

I am not a software developer.

I've spent more than 30 years around emerging technology—from the early Internet and open source through cloud computing and now AI. My background is technology strategy, operations, workflow, community, and building organizations around new technology.

I joke that I now consider myself a **Forward Deployed Architect**.

My definition is simpler than the title sounds:

> I understand the software-development lifecycle well enough to tell AI what needs to happen next.

Until recently, my GitHub was basically a ghost town.

Then coding agents changed the interface to software development.

I started applying what I knew about workflow, requirements, handoffs, reviews, failure recovery, and quality gates to AI agents that could write code.

That became The Gibson.

The lesson: generating code wasn't the hardest problem. The harder problem was engineering reliably—understanding requirements, choosing tools, staying in scope, responding correctly to failed tests, recovering, obtaining independent review, and knowing when evidence actually justified completion.

Mini Gibson asks:

> **Can a small open model learn how an organization engineers software?**

We started with NVIDIA Nemotron 3.5 Lightning, trained a LoRA adapter on curated engineering trajectories, and compared it with the base model under the same development evaluator. The tuned model resolved 16 of 48 issues versus 9 of 48 for the base model, but the difference did not cross the preset statistical boundary and malformed responses became worse. We did not promote the adapter.

That is why our deliverable is not a victory claim or a finished autonomous
developer. It is a reproducible training and evaluation pipeline that can keep
failed attempts, stop unsafe promotion, and tell us what to improve next. The
successor experiment is screening the same already-frozen 456-task package for evaluator
compatibility before another fine-tune or model comparison. Its terminal result
is still pending. That preflight is infrastructure evidence, not
model evidence, and the public final holdout remains operationally sealed and
unconsumed by the pipeline.

The model can change. The coding agent can change. The durable asset is the organization's accumulated engineering experience and the evidence system that enforces it.

**Mini Gibson — Small Model. Serious Engineer.**

See the [project map](PROJECT-MAP.md) for the exact repositories, models,
datasets, and proposed Langfuse and Jev follow-on work.
