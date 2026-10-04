# scripts/data

| Script | Purpose |
|---|---|
| `history_inventory.py` | Metadata-only inventory of Codex/Grok/Claude sessions already on disk, tagged by repo, branch and issue. Writes CSV to `~/gibson-traces/inventory/` and refuses to write inside a git worktree. |
| `trace_export.py` | Converts captured runs (Claude stream-json, Grok streaming-messages-json, Codex `exec --json`) to chat-format JSONL with normalized tool names, a time split, and a frozen held-out set. |
| `trace-scrub.sh` | Fail-closed scrub (gitleaks + redaction + quarantine). Required before any trajectory leaves the private store. |
| `run-record.v1.schema.json` | Per-run record with harness and outcome labels. |

Raw sessions and inventory CSVs never enter this repo. Only scrubbed, converted records do, after
`trace-scrub.sh` and the provenance/leakage validator.
