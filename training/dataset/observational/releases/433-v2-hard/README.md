# #433 observational dataset — v2 hard tranches (#440–#444)

Hard DEV-only tranche for #433, families #440–#444 (decoy navigation, coupled multi-file fixes, config precedence/state, test-failure diagnosis, premature-completion traps). Same pipeline as 433-v1 (`docs/433-agent-kit/`).
Schema: `training/dataset/observational/schema.observational.v0.1.json`.

| Field | Value |
|---|---|
| File | `runs.jsonl` (105 rows, 791,088 bytes) |
| sha256 | `3e181c6b6f4c6878558c75ee971471893603c50f627fc865c92ad509b63baf24` |
| Model | `nvidia/nemotron-3.5-lightning` via OpenRouter (provider: CoreWeave) |
| Runtime | `hermes-agent vgit.3b63f7b (2026.9.24)` |
| Collected | 2026-10-12 21:46 to 22:02 ET |
| Split | 105 `DEV_OBSERVATIONAL` (35 tasks) |
| Outcomes | 102 verified / 3 failed (`terminal_outcome`) |
| Tokens | 3,685,368 input / 358,757 output |
| Cost | $0.974901 total from summed `cost_usd` |

## Per family

| Family | Issue | Tasks | Rows | Verified | Failed |
|---|---|---|---|---|---|
| Decoy navigation | #440 | 7 | 22 | 22 | 0 |
| Coupled multi-file fixes | #441 | 7 | 21 | 21 | 0 |
| Config precedence / state | #442 | 7 | 21 | 21 | 0 |
| Test-failure diagnosis | #443 | 7 | 21 | 18 | 3 |
| Premature-completion traps | #444 | 7 | 20 | 20 | 0 |

The three failures are all `dev-hard-d-phone` (#443). Each edited `phones/fmt.py`, the independent verifier still failed `test_uk`, and the failure label is `unsuccessful_repair`.

Notes
- `ensure_pristine.py` exited 0 before the run (`OK reset fixtures from templates; 95 tasks; pristine for fix kinds`). Prompts were not tuned.
- `OBS_TARGET_ROWS=105` with 3 workers. A parallel append race at the cap left `dev-hard-a-tax-quote` with 4 rows and `dev-hard-e-url-join` with 2. Every other task has 3. All 35 tasks are present. Family row counts above match that.
- Every row has `provider=CoreWeave` and `provider_metadata.upstream_unique=["CoreWeave"]`.
- Hard spend cap was $10 (`OBS_SPEND_CAP_USD`). Summed `cost_usd` is $0.974901. OpenRouter `limit_remaining` on the shared key moved from $54.049921 at batch start to $53.053732 after the run (delta $0.996189), which also includes any other use of that key during the window.
- Secret scan of this directory before handoff: no OpenRouter key material, 1Password references, private-key blocks, or GitHub personal-access tokens.
- This release is not committed. TEST holdouts were not used.

- Host paths normalized after review: the collector temp root is written as `<OBS_ROOT>` and other temp paths as `<TMP>`. Byte count and sha256 above are for the normalized file.
