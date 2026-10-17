# Mini Gibson tool-calling evidence

These receipts contain scalar results from saved development runs and selected diagnostics. They contain no raw prompts, tool content, commands, diffs, changed filenames, voice identifiers, or absolute filesystem paths.

Run the offline check with Python 3 and its standard library:

```sh
python3 verify_tool_calling_evidence.py
```

The check verifies sanitized artifact hashes, pinned original-source hash references, model and adapter identity, per-batch harness identity, task pairing, deterministic pass consistency, token counters, selected residual task membership, and the summary recount. The original full receipts are not included or fetched; their hashes identify the source material and do not constitute a signature.

The next 24-task development cohort passed 3 tasks with the base model and 4 with the adapter. This is distinct from the previously reviewed 6-versus-12 cohort; their harness revisions differ. The selected 1,024-token retries passed 8 of 21 tasks, with four calls still malformed at the response limit. Retrying those four at 1,536 tokens passed two, with two still malformed. A test-file modification in the 1,024-token diagnostic was flagged and failed.

These are development findings and selected adapter-only diagnostics. Keep diagnostic retries separate from the original paired results and from final evaluation. Final quality gains and reduced human intervention remain pending. A shorter-call and recovery curriculum is proposed work, not a newly completed training run.

Local generation and tool traces exist in the original saved records. This bundle does not establish a connected hosted Langfuse session or a completed hosted Langfuse or Jev export. Local deterministic tests and change boundaries determine the recorded pass outcome.
