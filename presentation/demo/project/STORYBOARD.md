# Mini Gibson — current progress demo

## Frame 1 — Why is everything waiting for me?

Start: 0.000s. Duration: 10.961s.

Visual: Actual supplied GitHub graph, start date, then the human-bottleneck question.

Voiceover: I started vibecoding on February fourteenth, twenty twenty-six. AI helped me turn ideas into software. My GitHub graph turned green. Then I noticed a problem: the agents could keep building, but too much of the work still came back to me.

## Frame 2 — The old guys are dusting off their keyboards.

Start: 10.961s. Duration: 25.030s.

Visual: Real Mark and John portraits, supplied/corroborated leadership bios, old-guys keyboard line.

Voiceover: I'm Mark Hinkle, co-founder of All Things AI. I've been executive director of the Node.js Foundation, VP of developer relations at Cloud dot com, and VP of marketing at the Linux Foundation. John Willis co-wrote The DevOps Handbook. He led training and services at Opscode, now Chef, worked at Enstratius, acquired by Dell, and co-founded SocketPlane, acquired by Docker. We know process, but lately we've spent more time managing than coding. Today, the old guys are dusting off their keyboards.

## Frame 3 — Everything comes back to me.

Start: 35.991s. Duration: 11.894s.

Visual: Explain/Handoff/Check/Fix/Verify and waiting-for-me implication.

Voiceover: I'm explaining the same context, handing work between agents, checking results, and rescuing failed attempts. More code means more decisions waiting for me. The question is how to improve the system so the human doesn't become the bottleneck.

## Frame 4 — Can we keep work moving with less help?

Start: 47.885s. Duration: 16.869s.

Visual: Less human intervention plus small model and real work history. Final hypothesis pending.

Voiceover: Mini Gibson is our experiment. We want a small model to learn concrete handoffs, responses to failed tests, and evidence of what changed. We'll compare the base model, the model inside Gibson, and the tuned model inside Gibson. Our hypothesis is fewer requests for human help while the work meets the same quality bar.

## Frame 5 — Slow start. Real lessons. / Two tracks. Different evidence.

Start: 64.754s. Duration: 28.754s.

Visual: Opening: slow start, provider pressure and stalled builds; then transition to separate 7B completed rehearsal/vLLM serving and 30B loaded/development-tested evidence using Transformers/PEFT.

Voiceover: Getting started took longer than we expected. We hit overloaded providers and stalled builds. Once we got past that, we could run our datasets and learn from actual failures. Our seven B model completed twenty training steps on Brev, using one H one hundred and NeMo Automodel. Vee ell ell em serves that adapter and passed connection checks. Separately, thirty B Lightning has a loaded adapter and development results, tested with Transformers and PEFT. We keep their datasets and results separate.

## Frame 6 — Why The Gibson? / An engineering process

Start: 93.508s. Duration: 18.588s.

Visual: Supplied Hackers still and naming-origin joke; then transition to The Gibson logo, Task → Isolated change → Checks → Review. A post-run correction notes that the 30B model was subsequently connected and evaluated.

Voiceover: Why The Gibson? In Hackers, it's a ridiculous supercomputer run by a bunch of buffoons. We thought it was apropos. Our Gibson defines tasks, isolates changes, runs checks, and requires independent review. Gibson Environment runs the tools and checks results. Connecting the model is still ahead. The model proposes repairs; checks and approval rules stay in place.

## Frame 7 — Agent Kontrol: where work waits for us

Start: 112.096s. Duration: 15.498s.

Visual: Actual existing Agent Kontrol screenshot; working/finished/needs-you states.

Voiceover: This is our existing Agent Kontrol dashboard. It shows Claude, Grok, and Codex across the fleet: working, finished, or waiting for me. We can see where work gets stuck. The experiment asks whether a specialized model can reduce the work that needs our attention.

## Frame 8 — Good JSON wasn't enough.

Start: 127.594s. Duration: 19.569s.

Visual: Good JSON was not enough: 283 source records become 188 train/30 development rows after filtering and real tokenization at 2,048 tokens. A post-run correction notes that the 30B OpenHands training manifest was subsequently recovered and hash-attested.

Voiceover: The original voiceover says the 30B record still needs matching. The on-screen post-run correction supersedes that sentence: the v1 package recovered the attested manifest, verified all 94 optimizer steps, and bound it to every tuned evaluation row.

## Frame 9 — A connection is not a finished job.

Start: 147.163s. Duration: 33.589s.

Visual: Connection and required-tool checks pass, but real 7B coding task fails with no edit. Separate exploratory 30B development comparison: 6/24 base, 12/24 adapter. Final quality and human intervention remain unproven.

Voiceover: The current audio reports the tool-calling diagnostics. The final silent card adds the verified v1 comparison and the terminal successor boundary without changing the original spoken track.

## Frame 10 — Optional extensions — still proposed

Start: 180.752s. Duration: 16.282s.

Visual: Gym/Jev/Langfuse optional connections clearly proposed.

Voiceover: Three optional pieces could help. Nemo Gym would organize repeatable trials. Jev would turn locked results into advice for John and me to review. Langfuse would show the sequence of model calls, tools, and checks. Those connections are proposed; we're not claiming they're running.

## Frame 11 — Keep the work moving.

Start: 197.034s. Duration: 12.965s.

Visual: Keepworkmoving and public repository link; final quality gains pending.

Voiceover: We want useful work that passes checks and independent review, with less chasing and rescuing from us. That's how we keep the human from becoming the bottleneck. Follow the repository on screen.

## Tool-calling revision

Scene09 now reveals three successive beats: separate 7B task failure and 30B v7/v8 counts; selected response-limit diagnostics; then test-boundary failure and proposed training behavior. Scene10 distinguishes local traces used from proposed hosted connections. Final quality remains unproven.

## Post-run correction and final findings

Frames 6 and 8 carry explicit `POST-RUN UPDATE` labels that supersede two stale
spoken claims: the 30B model was connected and evaluated, and its exact
training-data manifest was recovered and hash-attested. A final silent card is
generated from the verified terminal `summary.json`; it reports the v1 result,
the 456-task preflight boundary, and the operationally sealed holdout.
