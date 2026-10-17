# Token-cap diagnostic: truncation was real, but it was not the whole problem

**Diagnostic evidence only. The frozen 48-task comparison and its `do_not_promote` decision remain unchanged.**

Every malformed tuned response in the frozen comparison ended exactly at the original 512-token generation limit. We therefore reran only those 21 affected development tasks with the same model, adapter, fixtures, prompts, tools, deterministic decoding, network isolation, and safety checks, changing only the maximum new tokens per turn.

At 1024 tokens, malformed responses fell from **21/21 selected tasks to 4/21**, and **8/21 passed** where all 21 original capped runs had failed. This confirms that the 512-token limit materially confounded the tuned arm. It does not make the adapter a clear upgrade: 13/21 still failed, 17 tasks produced execution errors, and one task attempted to edit a test file.

## Results

| Diagnostic condition | Tasks | Passed | Tasks with malformed response | Generations | Execution errors | Policy/test violations |
|---|---:|---:|---:|---:|---:|---:|
| Original 512-token tuned rows, selected after the fact | 21 | 0 | 21 | 21 | 0 | 0 |
| 1024-token rerun | 21 | **8** | **4** | 152 | 57 across 17 tasks | 1 task |
| 1536-token rerun of the four residual truncations | 4 | **2** | **2** | 18 | 2 | 0 |

The four 1024-token residual failures were `fresh-c-format-bytes`, `fresh-c-nested-update`, `fresh-d-luhn-check`, and `fresh-d-dependency-order`; each again ended exactly at 1024 tokens. At 1536 tokens, the latter two tasks passed. The first two still emitted malformed whole-function replacements ending exactly at 1536 tokens.

The 1024-token policy failure was `fresh-c-histogram-buckets`. It changed `tests/test_histogram.py` even though only `histogram.py` was allowed. The evaluator recorded `tests_tampered=true`, rejected the unauthorized path, and the task failed verification.

## Interpretation

Three distinct effects are now visible:

1. **Evaluator mismatch:** 512 tokens was too small for the adapter's learned XML tool-call style. It overstated the malformed-call regression.
2. **Learned verbosity:** the adapter often copied entire functions, docstrings, and examples into `old_str`/`new_str` arguments instead of making a compact edit. Raising the cap moved the failure boundary but did not remove this habit.
3. **Agent reliability:** after parsing succeeded, repeated invalid shell commands, ineffective edits, and one test-tamper attempt still prevented reliable completion.

The adaptive 1024→1536 sequence must not be reported as a new benchmark score. The 21 tasks were selected because they failed at 512, the cap changed after observing those failures, and only four residual tasks were run at 1536. The correct use is diagnosis: improve the training distribution and freeze a suitable cap before a new preregistered comparison.

No 2048-token run was performed. Two tasks still expanding to the new ceiling is evidence that unbounded cap escalation treats the symptom. The next run should train concise exact-schema edits, failure recovery, and test-preserving behavior, then use a fixed 1536-token cap and a fresh development cohort. Final holdouts remain sealed.

## Execution and integrity

- Model: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`
- Model revision: `a9904d24bcc1d289a1950fa9d2b978c47cf903b9`
- Inference adapter SHA-256: `a7c6f56ea24527816a0a2c4aa652b7e28e4766ba902deaebb9186727d9bda23c`
- 1024 evaluator SHA-256: `0b3a0832851bf408f2c3bf4f4928cd1afbdbb47d40eade7a8c493d49f49592ba`
- 1024 combined result SHA-256: `6e55224299d8613522e9d2f28b59efd1d28f828fb5e6138cd0d280dedc212518`
- 1536 evaluator SHA-256: `5d82507fbbb8237284cb952aac07e2aa5f748aa364a9d339cf526b612af87818`
- 1536 residual result SHA-256: `17840a37a3b89217e1efc609dca4a11ab323ee7fbcac6a10c372b1e4aa6e7b04`
- Runtime: 2x NVIDIA H100 PCIe, deterministic decoding, networkless containers

The 1024 run was split across the two GPUs: the first container wrote the first 11 lock-ordered tasks and was then stopped; the second completed the final 10 using `tail10-lock.json`. The combined file preserves the original 21-task lock order and contains exactly 21 unique task IDs. The 1536 run used a four-task residual lock and exited successfully.

Run `python3 verify_diagnostic.py` from this directory to validate hashes, task identity and order, outcome counts, cap hits, and the expected safety event.
