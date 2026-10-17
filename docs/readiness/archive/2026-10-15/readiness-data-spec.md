> **Archived snapshot from 2026-10-15; superseded, not an operational runbook.**
> Preserved during readiness consolidation on 2026-10-16. The text below records
> discovery and candidate proposals at that date, including stale PR state,
> pre-export measurements, superseded filenames and unapproved settings.
> PR #14 has since merged, and the exporter and CPU adapter now exist.
> Use the [current readiness index](../../README.md),
> [data preparation guide](../../../readiness-data-preparation.md), and
> [trainer interface guide](../../../readiness-trainer-interface.md).
> The current exporter's complete-batch response-order normalization supersedes
> the earlier strict-order proposal. Candidate parameters are not frozen by this
> archive. Hardware, GPU spend, release eligibility and protocol decisions remain
> unresolved; archived commands must not be used as launch instructions.

# Data readiness spec: v7 → Nemotron-renderable derived export

Status: SPEC v2, 2026-10-15, revised on coordinator review. Spec-writer executed nothing; every measurement below is attributed. Scope is one weekend. The export is derived and reversible; it changes no dataset schema, no v7 file, no benchmark.

## 1. Inputs (immutable)

| Input | Facts |
| --- | --- |
| `~/gibson-traces/sft/train-v7.jsonl` | 104 sessions, 283 windows, 59 PRs, 7,186,689 char-estimated tokens, mode 600 (STATS.md round 8) |
| `~/gibson-traces/sft/holdout-v7.jsonl` | 16 sessions, 43 windows, 12 PRs, cutoff `2026-10-12T02:26:20Z`, issue lineage disjoint |
| Record shape | `episode_id, repo, issue, pr, task, trajectory, outcome, provenance, messages, token_count, vendor, session_role, window_index, window_count` (`extract.py:1396-1411`) |
| Tool-call shape | OpenAI style, `tool_calls[].function.{name, arguments:str}`; names normalized by `TOOL_MAP` (`extract.py:51-72`), unknown names become `other:<name>` |
| Tokenizer pin (analysis only) | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` @ `a9904d24bcc1d289a1950fa9d2b978c47cf903b9`; `chat_template.jinja` sha256 prefix `58933db7` (coordinator). Not an inference pin. Only tokenizer and template files are needed |

Template facts (public read 2026-10-15; implementation re-verifies against downloaded file hashes): ChatML `<|im_start|>`/`<|im_end|>`, eos and pad `<|im_end|>`; tools render as XML inside the system turn; an assistant call renders as `<tool_call>\n<function=NAME>\n<parameter=KEY>\nVALUE\n</parameter>\n</function>\n</tool_call>` and applies `arguments|items`, so **arguments must be a mapping and a JSON string fails at render**; tool messages render as `<tool_response>…</tool_response>` grouped into one `user` turn, **`tool_call_id` is ignored and results pair with calls by position**; assistant content without `reasoning_content` is prefixed `<think></think>`; `truncate_history_thinking` defaults true; there is no `raise_exception`, so our checks must be stricter than the template.

## 2. Measured state (coordinator, exact local public tokenizer at a9904d24, template 58933db7)

- Both v7 source file hashes unchanged.
- 29 train windows carry 71 unparseable `arguments` strings. Quarantining them whole leaves 254 windows / 102 sessions / 57 PRs. Most affected sessions keep other windows; the loss is not 104 minus 29 sessions.
- The 254 parseable windows render. Exact lengths: median 33,535, p95 38,837, max 41,458. 144 exceed 32,768. 247 exceed 4,096.
- The native assistant-mask API of the template returns all-zero masks: the template has no generation markers.
- Root cause of the 71 strings is unproven (source defect vs `redact.py:268-273` rewrite vs `shrink_arguments`/`fit_group`, `extract.py:1048-1070, 1104-1120`). The export classifies by shape and does not guess.

## 3. Local choices (authorized readiness work, not owner decisions)

- Malformed arguments or broken call/result closure: whole-window quarantine with reasons. No repair, no prefix truncation, no invented calls.
- Structurally valid windows are re-windowed to an exact-token cap. An assistant message with its ordered tool responses is one atomic bundle and is never split. A later `user` message stays attached to the assistant group that follows it, in source order. Each sub-window carries the window's `system` and first `user` task verbatim and is labelled `partial_context: true` with `source_window_index`, `part_index`, `part_count`. A bundle that alone exceeds the cap minus prefix is quarantined with `bundle_over_cap` and counted; a prefix that alone exceeds the cap quarantines the window with `prefix_over_cap`. Every input group ends in exactly one place, a kept sub-window or a quarantine row; the manifest proves it by count and by id.
- Cap is a required CLI value (`--max-window-tokens`). Reference inspection candidate uses 4096 so the pipeline is exercised on a cap that 247 of 254 windows exceed. No value is claimed to fit any hardware; the training length is chosen later with GPU evidence.
- No tool declarations in the inspection candidate (`tools=None`). Observed argument keys per tool name are recorded in `inventory.json` as diagnostics only and must not define any inference harness. Runtime tool conformance stays NO_GO until a frozen tool contract exists.
- `other:*` tool names are counted, not filtered, in the inspection candidate.

## 4. Outputs (outside the repo, mode 600, through `output_allowed`/`open_private`, `extract.py:1280-1302`)

```
~/gibson-traces/sft/derived/v7-nemotron-<run_id>/
  inventory.json        counts only, no content
  train.derived.jsonl   kept sub-windows, §5.5 shape
  holdout.meta.json     holdout-v7 metadata and hashes only: episode_id, repo, pr, issue, source_line_sha256, counts; no messages, no render, no export
  quarantine.jsonl      episode_id, window_index, reasons[], source_line_sha256; no content
  manifest.json         §6
  REPORT.md             counts and verdict only
```

v7 files are never modified. Removing the directory restores the prior state. Every kept or quarantined row maps to its v7 line by `(episode_id, source_line_sha256)`.

## 5. Pipeline (`training/historical/derive_nemotron.py`; stdlib plus pinned `tokenizers`, `transformers`, `jinja2`)

### 5.1 Inspect
Per call, exactly one class: `json_object`, `json_non_object`, `json_invalid`, `empty_or_braces`, `truncated_marker` (`{"truncated": true}` or `\n[truncated]` inside a value). Per tool name: observed top-level keys and JSON value types (diagnostic). Closure per bundle: an assistant message with N calls is followed by exactly N `tool` messages whose `tool_call_id`s equal the call ids in order; no extra, missing, or orphan `tool` (`group_messages` admits mismatches at `extract.py:1137` and drops orphans at `:1144-1146`). Count `[truncated]` tool outputs. Reads private text to classify it, prints only counts.

### 5.2 Quarantine (whole window)
Any of: a call not `json_object`; `truncated_marker`; closure failure; `messages[0]` not `system` or `messages[1]` not `user`; assistant message with empty content and no calls; `check_record` failure; grammar collision (§5.4).

### 5.3 Normalize (proven-equivalent only)
`arguments` string → `json.loads` → `dict`, accepted only when `json.dumps(obj, sort_keys=True, separators=(",", ":"))` equals the same canonical dump of `json.loads(s)`. Nothing else is rewritten. `content` passes through byte-identical.

### 5.4 Grammar collision
Any message `content` or argument value containing `<|im_start|>`, `<|im_end|>`, `<SPECIAL_`, `[INST]`, `[/INST]`, `[AVAILABLE_TOOLS]`, `[TOOL_CALLS]`, `[TOOL_RESULTS]`, `<tool_call>`, `</tool_call>`, `<tool_response>`, `</tool_response>`, `<function=`, `</function>`, `<parameter=`, `</parameter>`, `<think>`, `</think>` quarantines the window with `grammar_collision`. The template would render such text as control structure.

### 5.5 Render and mask (instrumentation, not native support)
Load tokenizer and the original `chat_template.jinja` from a local snapshot; record sha256 of every file; mismatch or load error aborts. Render with `add_generation_prompt=False`, `enable_thinking=False`, `truncate_history_thinking=False`; if any historical assistant turn is rewritten, abort. Because the native mask is all zero, masking uses a separately hashed instrumented template that adds only Jinja generation markers around assistant bodies and their EOS, nothing else. The coordinator's independent synthetic probe on 5 cases showed identical rendered text and token IDs between native and instrumented templates, positive assistant targets, and zero user/tool targets. Production must implement this independently, pin both template hashes and the exact anchor edits in the manifest, and on every real record verify byte equality of rendered text and equality of token IDs between native and instrumented renders; any difference is a hard fail of the run. No delimiter search, no prefix-delta span mapping. If the instrumentation cannot be verified, the export writes `input_ids` without `labels` and REPORT.md states masking NO_GO. Output row: `input_ids`, `labels` (or absent), `episode_id`, `source_window_index`, `part_index`, `part_count`, `partial_context`, `exact_tokens`, `target_tokens`, `provenance` (v7 list unchanged). Assistant targets include the literal `<think></think>` prefix because no `reasoning_content` exists and none is fabricated; REPORT.md says so.

### 5.6 Development split (train only, optional)
If a LoRA run needs it: 10% of kept train `(repo, pr)` keys by `mergedAt` latest first, expanded by `expand_holdout_by_issue`, seed 414, then `assert_holdout_disjoint` against dev and `holdout-v7`, and `bench/check_contamination.py` against the kept train PR set. `holdout-v7` is touched only through `repo`, `pr`, `issue`, `episode_id`, and line hashes (`holdout.meta.json`); its messages are never read, rendered, or exported by this pipeline. Gibson Bench v0.1 is never read for any decision.

## 6. Manifest

`run_id`, UTC time, repo git SHA, source paths and sha256 with line counts; tokenizer repo and revision; sha256 of each tokenizer file, the original template, the instrumented template, and the anchor diff; pinned library versions; `--max-window-tokens`; render flags; counts: windows in, quarantined by reason and unique, structurally valid, sub-windows written, bundles quarantined over cap, groups in equals groups placed plus groups quarantined; sessions and PRs kept; exact and target token totals; secret re-scan of derived outputs via `residual_json_text` (must be 0); contamination result; per-row table `{episode_id, source_window_index, part_index, source_line_sha256, status, reasons, exact_tokens, target_tokens, native_instrumented_equal}`; `verdict`.

## 7. Verdicts

- `INSPECTION_PASS`: §5.1 completed on every line, every call classified, inventory written.
- `RENDER_PASS`: every kept sub-window rendered, native/instrumented equality held on every row, secret re-scan 0, contamination 0, disjointness asserted, conservation count holds.
- There is no CPU-side training GO. Training remains NO_GO until: a frozen tool contract and runtime tool conformance; the Megatron custom-data loader accepts the export at runtime (a synthetic no-weights CPU container smoke may prove the container and torch loader import; actual loader runtime stays NOT_RUN until it runs); A/B baseline captured. Mark's decisions recorded 2026-10-15: GPU commands may be prepared but WAIT TO LAUNCH; the corpus stays private. Any change to the review gate is Mark's. Nothing else in this document waits on Mark.
Any tokenizer, template, JSON, or I/O error that is not a named quarantine reason exits non-zero and writes only REPORT.md.

## 8. Tests (`tests/historical/test_derive.py`, unittest, offline)

Argument classes incl. nested object and truncated marker; canonical round-trip accept/reject; closure cases (missing, extra, out-of-order, orphan, absorbed mismatch); grammar-collision strings; re-windowing: bundle atomicity, later-user attachment order, prefix carried, `partial_context` labels, conservation (groups in == placed + quarantined), oversize bundle and oversize prefix reasons; reversibility (kept ∪ quarantined == input ids, no content in quarantine); output path refusal and mode 600. Renderer and mask tests run only with `GIBSON_TOKENIZER_DIR` whose sha256s match the pins, otherwise `skipTest` reported as SKIPPED, never PASS; the CLI refuses `RENDER_PASS` under skip. Native/instrumented equality is asserted on fixtures with the real tokenizer only; stub-tokenizer tests are labelled structural and assert no counts.

## 9. Out of scope

Root-causing the 71 strings; editing `extract.py` or redaction; episode reweighting; negatives and assessor files; choosing the training length; any release (corpus is private by Mark's decision, 2026-10-15).
