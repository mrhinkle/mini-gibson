# Mini Gibson demo — keep the work moving

Can a specialized small model help AI development move forward without every
handoff, failed check, and repair waiting for a person?

[Watch or download the narrated MP4](mini-gibson-demo.mp4) ·
[Transcript](transcript.txt) · [Captions](captions.srt) ·
[Editable project ZIP](mini-gibson-demo-project.zip)

[Plain-language submission summary](../../SUBMISSION.md) ·
[Project and public-dataset map](../../docs/PROJECT-MAP.md)

[![Tool-calling lessons](poster.png)](mini-gibson-demo.mp4)

This approximately 3:30 demo introduces Mark Hinkle and John Willis, the human
bottleneck, The Gibson, Agent Kontrol, the two model/data tracks, vLLM, and the
proposed NeMo Gym, Jev, and Langfuse connections. Narration uses Mark's authorized
ElevenLabs voice clone. The editable project uses the frozen audio; no voice API
credential is required to replay or render it.

The original spoken track predates the final v1 evidence. Two explicit
`POST-RUN UPDATE` overlays correct its superseded “model connection pending”
and “training record unmatched” statements. The final render also appends a
silent findings card generated from the terminal successor summary; the
transcript labels that correction rather than pretending it was in the frozen
voice recording.

The “Why The Gibson?” segment uses Mark's supplied still from *Hackers* (1995) and his self-deprecating naming joke, then returns to the engineering process. The [film/image source note](evidence/gibson-name-source.json) records the attribution and asset hash.

The updated tool-calling and observability sections use Mark's authorized voice clone, fitted to the original 3:30 narrated cut with pitch preserved. Captions and visual cues are synchronized, with a three-second closing hold. The terminal findings card adds 14 silent seconds, bringing the authored deliverable to 3:44. See the [audio pacing record](project/audio_meta.json).

## What the slow start taught us

Mark reports overloaded providers; the records also document stalled/failed builds and an unavailable container image. Once the team got runs working, the data exposed broken examples and cases where the token limit removed the answer. The next lesson was behavioral: a model can answer and return a valid tool call while still failing to finish a real repository task. The [startup source note](evidence/startup-lessons-source.json) separates Mark's account from the logged setup problems.

## Progress reviewed on October 17, 2026

| Track | What the records establish | What remains unproven |
| --- | --- | --- |
| OpenCodeReasoning-Nemotron-7B | 20-step LoRA rehearsal on Brev H100; 188 train / 30 dev rows from 283 source records, at a 2,048-token limit. The subsequent execution report records vLLM 0.11.0 health, model-listing, chat and required-tool checks passing. | The first real repository coding task failed and applied no edit. Endpoint checks do not establish autonomous engineering competence. |
| Nemotron 3.5 Lightning 30B | A loaded adapter was evaluated with Transformers/PEFT. The first v7 development batch passed **6/24 base** and **12/24 adapter**; a fresh v8 batch passed **3/24 base** and **4/24 adapter**. The later v1 package recovered the attested training-data manifest and the complete 94-step training record, then froze the paired result at **9/48 base** and **16/48 tuned**. | These are development observations, not final-holdout results. The exact paired uplift missed the preset statistical boundary, and malformed-response incidence became worse, so the adapter was not promoted. |

**The counts are development observations. Final held-out quality, promotion
readiness, and reduced human intervention remain unproven.** The 7B and 30B
tracks use different data and execution paths. The 30B results are not a vLLM
result. The 7B run does not establish 30B training; the later attested v1
evidence package does establish the completed 94-step 30B run.

The [evidence directory](evidence/README.md) contains sanitized result rows,
source hashes, the archived v7 provenance lock, a public summary of the original
7B rehearsal receipt, its metric files, and an endpoint execution-report summary.
It excludes corpus text, conversations, generated diffs, credentials and hostnames.
The 7B endpoint summary is documentary evidence; no live endpoint was reprobed
while producing this demo. The earlier 94-step configuration alone was not a
receipt; the later v1 evidence package supplied the verified 94/94 record.

The recovered v1 training manifest identifies
[`nvidia/SWE-Hero-openhands-trajectories`](https://huggingface.co/datasets/nvidia/SWE-Hero-openhands-trajectories)
at revision `150bc119e52c647216fce285fd801f16b6fd745b`, with 188 training and 30
development examples. The manifest is hash-attested in every tuned v1 row. No
source corpus or model weights are included here.

## What tool calling taught us

Across the two saved 30B development batches, **21 adapter tasks produced malformed output at the 512-token response limit**. Selected adapter-only retries at 1,024 tokens passed **8/21** tasks, with four still malformed. Retrying those four at 1,536 tokens passed **2/4**, with two still malformed. These are diagnostics on selected failures; their passes are not added to the paired development scores.

The 21 cut-off outputs comprise six from the earlier v7 source receipts and 15 from the fresh v8 batch. The new verifier recounts v8 and the selected retries; the existing v7 evidence remains separate.

More response space helped, but it did not fix the whole problem. One 1,024-token attempt modified a test file, was flagged by the boundary check, and remained failed. The two successful 1,536-token residual tasks recovered after a tool error. The next proposed training examples focus on shorter valid calls, inspecting files before editing, recovery, and preserving tests. No new fine-tune was run for this video.

The [tool-calling evidence summary](evidence/tool-calling/summary.json) and [sanitized receipts](evidence/) retain counts, source hashes and limitations. Local generation/tool trace records informed this analysis. No hosted Langfuse export or authenticated Jev call is evidenced; hosted Langfuse, Jev and NeMo Gym remain proposed connections.

## Inspect and replay

Recount the committed receipts without running a model:

```bash
python3 presentation/demo/verify_evidence.py
python3 presentation/demo/verify_tool_calling_evidence.py
```

Open the editable video:

```bash
cd presentation/demo/project
npm run dev
```

Render from the pinned HyperFrames 0.8.171 project:

```bash
npm run render -- --quality delivery --output ../mini-gibson-demo.mp4
```

Node.js 22 or newer and FFmpeg are required. The first `npx` invocation may fetch
the pinned CLI. The project includes its audio, screenshots, logos, backgrounds,
and the Arimo and Archivo Black fonts with their upstream license notices and
[source hashes](project/assets/fonts/SOURCES.json).

[Media verification](verification.json) records dimensions, runtime, audio,
full-file decoding, and comparisons with inspected preview frames. The
[file manifest](FILES.sha256.json) records the published artifact hashes.
