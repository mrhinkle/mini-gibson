# #433 observational dataset — v1 (full run)

Full observational run set for #433, collected with the pipeline from the #433 agent kit (`docs/433-agent-kit/`, PR #10).
Schema: `training/dataset/observational/schema.observational.v0.1.json`.

| Field | Value |
|---|---|
| File | `runs.jsonl` (1,000 rows, 6,783,720 bytes) |
| sha256 | `61becc2590dda4a2cdf974b763a2e887dcda37cdfcb732f5ff144c78e0b0768a` |
| Model | `nvidia/nemotron-3.5-lightning` via OpenRouter (provider: CoreWeave) |
| Runtime | `hermes-agent v0.21.5+7252.g8030911` |
| Collected | 2026-10-05 16:54 to 21:52 ET |
| Split | 827 `DEV_OBSERVATIONAL` (124 tasks) / 173 `TEST_OBSERVATIONAL` (26 tasks) |
| Outcomes | 926 verified / 74 failed (`terminal_outcome`) |
| Tokens | 8,756,436 input / 1,583,554 output |
| Cost | $5.60 total from summed `cost_usd` ($4.64 DEV / $0.96 TEST) |

Notes
- This release is committed at a versioned path on purpose. The working output path
  `training/dataset/observational/runs.jsonl` stays git-ignored for future runner output.
- Secret scan before commit: no API keys, tokens, `op://` references, or private keys found.
  The only pattern hits were false positives: "ta**sk-sc**heduler" prose and `Authorization: Bearer <placeholder>` doc text from fixtures.
- TEST rows are held out. Do not train on them.
