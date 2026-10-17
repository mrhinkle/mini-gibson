# Mini Gibson — current progress demo

## Frame 1 — Why is everything waiting for me?

Start: 0.000s. Duration: 12.092s.

Visual: Actual supplied GitHub graph, start date, then the human-bottleneck question.

Voiceover: I started vibecoding on February fourteenth, twenty twenty-six. AI helped me turn ideas into software. My GitHub graph turned green. Then I noticed a problem: the agents could keep building, but too much of the work still came back to me.

## Frame 2 — The old guys are dusting off their keyboards.

Start: 12.092s. Duration: 27.612s.

Visual: Real Mark and John portraits, supplied/corroborated leadership bios, old-guys keyboard line.

Voiceover: I'm Mark Hinkle, co-founder of All Things AI. I've been executive director of the Node.js Foundation, VP of developer relations at Cloud dot com, and VP of marketing at the Linux Foundation. John Willis co-wrote The DevOps Handbook. He led training and services at Opscode, now Chef, worked at Enstratius, acquired by Dell, and co-founded SocketPlane, acquired by Docker. We know process, but lately we've spent more time managing than coding. Today, the old guys are dusting off their keyboards.

## Frame 3 — Everything comes back to me.

Start: 39.704s. Duration: 13.121s.

Visual: Explain/Handoff/Check/Fix/Verify and waiting-for-me implication.

Voiceover: I'm explaining the same context, handing work between agents, checking results, and rescuing failed attempts. More code means more decisions waiting for me. The question is how to improve the system so the human doesn't become the bottleneck.

## Frame 4 — Can we keep work moving with less help?

Start: 52.825s. Duration: 18.609s.

Visual: Less human intervention plus small model and real work history. Final hypothesis pending.

Voiceover: Mini Gibson is our experiment. We want a small model to learn concrete handoffs, responses to failed tests, and evidence of what changed. We'll compare the base model, the model inside Gibson, and the tuned model inside Gibson. Our hypothesis is fewer requests for human help while the work meets the same quality bar.

## Frame 5 — Slow start. Real lessons. / Two tracks. Different evidence.

Start: 71.434s. Duration: 31.720s.

Visual: Opening: slow start, provider pressure and stalled builds; then transition to separate 7B completed rehearsal/vLLM serving and 30B loaded/development-tested evidence using Transformers/PEFT.

Voiceover: Getting started took longer than we expected. We hit overloaded providers and stalled builds. Once we got past that, we could run our datasets and learn from actual failures. Our seven B model completed twenty training steps on Brev, using one H one hundred and NeMo Automodel. Vee ell ell em serves that adapter and passed connection checks. Separately, thirty B Lightning has a loaded adapter and development results, tested with Transformers and PEFT. We keep their datasets and results separate.

## Frame 6 — The Gibson: a process the model can learn

Start: 103.154s. Duration: 22.157s.

Visual: The Gibson engineering-process diagram. Model connection remains pending.

Voiceover: The Gibson is our process framework: define the task, isolate changes, run checks, and get independent review. Gibson Environment is the foundation that runs tools and checks their results. Connecting it to this model is still ahead. The model proposes repairs. Independent review and our approval rules stay in place.

## Frame 7 — Agent Kontrol: where work waits for us

Start: 125.311s. Duration: 17.097s.

Visual: Actual existing Agent Kontrol screenshot; working/finished/needs-you states.

Voiceover: This is our existing Agent Kontrol dashboard. It shows Claude, Grok, and Codex across the fleet: working, finished, or waiting for me. We can see where work gets stuck. The experiment asks whether a specialized model can reduce the work that needs our attention.

## Frame 8 — Good JSON wasn't enough.

Start: 142.408s. Duration: 21.588s.

Visual: Good JSON was not enough: 283 source records become 188 train/30 development rows after filtering and real tokenization at 2,048 tokens. Separate 30B OpenHands training record remains unmatched.

Voiceover: For the seven B rehearsal, two hundred eighty-three source records became one hundred eighty-eight training rows and thirty development rows. Some examples were broken; others lost the answer at the token limit. We saved and reloaded a small LoRA adapter. The thirty B OpenHands track still needs its training-data record matched to the evaluated adapter.

## Frame 9 — A connection is not a finished job.

Start: 163.996s. Duration: 37.054s.

Visual: Connection and required-tool checks pass, but real 7B coding task fails with no edit. Separate exploratory 30B development comparison: 6/24 base, 12/24 adapter. Final quality and human intervention remain unproven.

Voiceover: Our biggest lesson: a working connection isn't a finished job. The seven B adapter passed a required tool call, but failed a real repository change. Automatic mode returned prose; forced calls repeatedly targeted the wrong file. No edit was applied. In the separate thirty B development run, the base passed six of twenty-four tasks; the adapter passed twelve. Those are exploratory development results. We still need to match the training records, lock the comparison, and test on untouched tasks. Better quality and fewer human interruptions are still unproven.

## Frame 10 — Optional extensions — still proposed

Start: 201.050s. Duration: 17.962s.

Visual: Gym/Jev/Langfuse optional connections clearly proposed.

Voiceover: Three optional pieces could help. Nemo Gym would organize repeatable trials. Jev would turn locked results into advice for John and me to review. Langfuse would show the sequence of model calls, tools, and checks. Those connections are proposed; we're not claiming they're running.

## Frame 11 — Keep the work moving.

Start: 219.012s. Duration: 13.994s.

Visual: Keepworkmoving and public repository link; final quality gains pending.

Voiceover: We want useful work that passes checks and independent review, with less chasing and rescuing from us. That's how we keep the human from becoming the bottleneck. Follow the repository on screen.
