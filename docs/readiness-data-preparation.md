# Local transcript-SFT preparation

This CPU preparation produces a **private inspection candidate**, with exact
token lengths and assistant-only labels. It does not train a model or establish
Megatron loader acceptance, runtime tool conformance, GPU fit, serving, or release
permission. Those stages remain `NO_GO` in every completed manifest.

Use `python -m training.historical.prepare` from the repository root. The isolated
CPU environment must match `requirements-tokenization.txt`; torch, model weights,
network fallback and remote tokenizer code are not required or enabled.

```bash
python -m training.historical.prepare \
  --source /private/source/train-v7.jsonl \
  --holdout /private/source/holdout-v7.jsonl \
  --tokenizer /private/readiness/tokenizer \
  --training-keys /repo/bench/contamination/train-v7.keys.json \
  --benchmark-dir /repo/bench/tasks \
  --output /private/readiness/prepared-v8-r2 \
  --max-tokens 4096
```

All paths and the sequence cap are explicit. The tokenizer directory must contain
the verified `download-manifest.json` plus the five pinned public tokenizer/config
files. The model revision is
`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` at
`a9904d24bcc1d289a1950fa9d2b978c47cf903b9`. No weight files are downloaded. Missing
or modified artifacts, dependency-version drift and template failures stop the
export. Original training and holdout files are hashed before and after preparation
and checked again before the completion seal becomes visible. Holdout message
content is never normalized or tokenized; only hashes and split identifiers are
used.

## Structural policy and the response-order correction

An original source window is the structural-quarantine unit. Malformed, scalar,
partial, trailing-data or duplicate-key JSON arguments quarantine the whole
window. There is no argument repair. Valid JSON-object arguments become mappings
because the native template iterates their fields. Tool names do not establish
supported runtime tools, and no tool schemas are inferred or supplied.

The adopted normalization differs narrowly from the first strict-order proposal.
The native template renders tool responses without their IDs, so preserving a
permuted arrival order could silently associate an output with the wrong call.
For a **complete contiguous batch only**, whose unique response-ID set exactly
equals the immediately preceding assistant's unique call-ID set, the exporter
keeps the assistant call array unchanged and reorders its tool response messages
into that call order. Every response content and ID value is preserved. Source
arrival order remains recoverable from the original immutable file and the
ledger's source/rendered message indices. Manifest counts distinguish normalized
validated batches from normalized batches retained in the candidate.

Missing, duplicate, orphan or interrupted batches remain whole-window quarantines.
The exporter never moves a response across another assistant, user or system
message. It rejects raw role/control tokens and tool-grammar closing-tag collisions
before rendering, including such delimiters hidden in JSON Unicode escapes.

The private first `prepared-v8` attempt used the superseded strict-order policy
and is **not the selected training candidate**. Keep it as a superseded diagnostic
artifact. A corrected execution uses a fresh `prepared-v8-r2` directory; existing
destinations are never overwritten.

## Packing and masks

The original system message and initial user task are repeated in every derived
window. A tool group includes the assistant's complete call batch and every
matching response. Later user/system messages stay paired with the following
assistant group. Greedy packing uses the exact rendered token count at the
explicit cap. It excludes oversized atomic groups rather than slicing arbitrary
text or token arrays. Derived continuations and gaps have `partial_context=true`;
there are no generated summaries. Groups without observed assistant content are
excluded. Every input group receives exactly one kept/quarantined disposition
and primary reason in `groups.jsonl`.

The pinned native template has no generation metadata and returns an all-zero
native assistant mask. The exporter adds only Jinja generation metadata around
the native assistant body/EOS branches, with exact unique anchors and a separately
recorded template hash. It then uses Transformers' generation-span mask support.
For **every rendered candidate**, the instrumented and native rendered strings
and input IDs must be exactly equal. Masks must match input length, contain only
zero or one, and retain positive next-token assistant targets. A failed equality
or mask check stops the export. Loss spans are never found by delimiter search
or blind conversation-prefix differences.

`train.jsonl` contains the original provenance, unique prepared IDs, source IDs,
messages, rendered text, exact `input_ids`, unshifted HF-style `labels`, and actual
token counts. Non-assistant positions have label `-100`. Tool-argument insertion
order is preserved in the saved messages so re-rendering does not change the
parameter order used for tokenization. Original message text is preserved apart
from the native template's own formatting and the explicit response-order rule.
The model template may add its native empty thinking markup.

## Output integrity and interpretation

The new directory has mode `0700`; every output file has mode `0600`. Source/output
overlap and existing destinations are rejected. Files are written privately in a
staging directory, then transferred into an exclusively created destination.
`COMPLETED.sha256` is transferred last. **A directory or manifest without a valid
completion seal is unfinished.** Check the seal against `manifest.json` and its
artifact hashes before consuming any data. Interrupted or failed output must not
be mistaken for a complete export; select a new destination for any retry.

The manifest records input/output hashes, exact token and target counts,
source-window/session/PR retention, group and message exclusions, normalization
counts, tokenizer/template/dependency pins and named stage results. The original
59-PR key list is the allowed training universe. Retained PR/session/issue keys
must remain a subset of the original source and be disjoint from holdout and
benchmark keys. These checks do not establish exhaustive absence of textual
leakage or authorize releasing private operational material. Historical merged
outcomes are provenance, not independent software verification of every window.

Unit tests use synthetic messages and fake renderers where appropriate. They
prove structural and file-policy behavior, not real-model compatibility. The
full private CPU execution with the pinned tokenizer supplies separate rendering,
length and native-equivalence evidence. A downstream trainer must still accept
the actual exported records and preserve their supervision masks; JSONL creation
alone does not close that gate. GPU commands must remain prepared and unlaunched
until Mark explicitly starts the hardware rehearsal.
