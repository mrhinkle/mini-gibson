# Mini Gibson — current progress demo

## Frame 1 — Why is everything waiting for me?

Start: 0.000s. Duration: 12.817s.

Visual: Actual supplied GitHub graph, start date, then the human-bottleneck question.

Voiceover: I started vibecoding on February fourteenth, twenty twenty-six. AI helped me turn ideas into software. My GitHub graph turned green. Then I noticed a problem: the agents could keep building, but too much of the work still came back to me.

## Frame 2 — The old guys are dusting off their keyboards.

Start: 12.817s. Duration: 29.269s.

Visual: Real Mark and John portraits, supplied/corroborated leadership bios, old-guys keyboard line.

Voiceover: I'm Mark Hinkle, co-founder of All Things AI. I've been executive director of the Node.js Foundation, VP of developer relations at Cloud dot com, and VP of marketing at the Linux Foundation. John Willis co-wrote The DevOps Handbook. He led training and services at Opscode, now Chef, worked at Enstratius, acquired by Dell, and co-founded SocketPlane, acquired by Docker. We know process, but lately we've spent more time managing than coding. Today, the old guys are dusting off their keyboards.

## Frame 3 — Everything comes back to me.

Start: 42.086s. Duration: 13.908s.

Visual: Explain/Handoff/Check/Fix/Verify and waiting-for-me implication.

Voiceover: I'm explaining the same context, handing work between agents, checking results, and rescuing failed attempts. More code means more decisions waiting for me. The question is how to improve the system so the human doesn't become the bottleneck.

## Frame 4 — Can we keep work moving with less help?

Start: 55.994s. Duration: 19.819s.

Visual: Less human intervention plus small model and real work history. Final hypothesis pending.

Voiceover: Mini Gibson is our experiment. We want a small model to learn concrete handoffs, responses to failed tests, and evidence of what changed. We'll compare the base model, the model inside Gibson, and the tuned model inside Gibson. Our hypothesis is fewer requests for human help while the work meets the same quality bar.

## Frame 5 — Two tracks. Different evidence.

Start: 75.813s. Duration: 20.770s.

Visual: Separate7Bcompletedrehearsal/vLLMserving from30Bloaded/dev-tested using Transformers/PEFT.

Voiceover: We now have two tracks. Our seven B model completed twenty training steps on Brev, using one H one hundred and NeMo Automodel. Vee ell ell em serves that adapter and passed connection checks. Separately, thirty B Lightning has a loaded adapter and development results, tested with Transformers and PEFT. We keep their datasets and results separate.

## Frame 6 — The Gibson: a process the model can learn

Start: 96.583s. Duration: 18.366s.

Visual: The Gibson engineering-process diagram. Model connection remains pending.

Voiceover: The Gibson is our process framework: define the task, isolate changes, run checks, and get independent review. Gibson Environment is the foundation that runs tools and checks their results. Connecting it to this model is still ahead. The model proposes repairs. Independent review and our approval rules stay in place.

## Frame 7 — Agent Kontrol: where work waits for us

Start: 114.949s. Duration: 16.754s.

Visual: Actual existing Agent Kontrol screenshot; working/finished/needs-you states.

Voiceover: This is our existing Agent Kontrol dashboard. It shows Claude, Grok, and Codex across the fleet: working, finished, or waiting for me. We can see where work gets stuck. The experiment asks whether a specialized model can reduce the work that needs our attention.

## Frame 8 — Our data and the open-data track.

Start: 131.703s. Duration: 23.858s.

Visual: 7B283source→188train/30dev,2048window; distinctOpenHandsdata track with unmatched30Btrainingrecord.

Voiceover: For the seven B rehearsal, we started with two hundred eighty-three source records. Filtering and tokenization left one hundred eighty-eight training rows and thirty development rows, at a two thousand forty-eight token limit. We saved and reloaded a small LoRA adapter. The separate OpenHands track still needs its training-data record matched to the evaluated adapter.

## Frame 9 — A connection is not a finished job.

Start: 155.561s. Duration: 33.856s.

Visual: 7Bendpoint PASS/coding FAIL/noedit.30Bexploratory6/24base and12/24adapter. Trainingrecords unresolved; finalquality/humanhelpunproven.

Voiceover: Working connections did not mean working software. The seven B adapter passed a required tool call, but failed a real repository change. Automatic mode returned prose; forced calls repeatedly targeted the wrong file. No edit was applied. In the separate thirty B development run, the base passed six of twenty-four tasks; the adapter passed twelve. Those are exploratory development results. We still need to match the training records, lock the comparison, and test on untouched tasks. Better quality and fewer human interruptions are still unproven.

## Frame 10 — Optional extensions — still proposed

Start: 189.417s. Duration: 16.800s.

Visual: Gym/Jev/Langfuse optional connections clearly proposed.

Voiceover: Three optional pieces could help. Nemo Gym would organize repeatable trials. Jev would turn locked results into advice for John and me to review. Langfuse would show the sequence of model calls, tools, and checks. Those connections are proposed; we're not claiming they're running.

## Frame 11 — Keep the work moving.

Start: 206.217s. Duration: 13.564s.

Visual: Keepworkmoving and public repository link; final quality gains pending.

Voiceover: We want useful work that passes checks and independent review, with less chasing and rescuing from us. That's how we keep the human from becoming the bottleneck. Follow the repository on screen.
