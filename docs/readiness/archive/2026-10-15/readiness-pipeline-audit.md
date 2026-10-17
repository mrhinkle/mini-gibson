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

# Readiness pipeline audit (discovery)

Date: 2026-10-15. Worktree: `/Users/mrhinkle/Code/mini-gibson-wt/readiness-pipeline-20261015`. HEAD `8156af0896e11b2494898d79c6fd1961b1240f31` (ancestor of named base `8156af0`). Read-only except this file. No GPU run, weight download, or corpus read. This is evidence for a coder lane, not an approval to train.

## What this checkout already runs

`training/historical/extract.py` writes private JSONL under `~/gibson-traces` or the temp dir (mode 600). Each window is OpenAI `messages` (`system`/`user`/`assistant`/`tool`, function tool calls) plus episode metadata. `training/dataset/schema.json` requires episode fields only. `validate.py` checks message roles and a `token_count`. That count is `len(text)//4` (`EPISODE_TOKEN_LIMIT=32768`, `TOOL_TOKEN_LIMIT=4096`). There is no loss-mask field, no chat-template render, and no model tokenizer.

`training/historical/STATS.md` (generated 2026-10-13T11:20:19Z) records train-v7 as 104 episodes / 283 windows / 7,186,689 estimated tokens and holdout-v7 as 16 episodes / 43 windows / 1,130,030. The JSONL files were not opened.

`pyproject.toml` depends on `PyYAML==6.0.3` and does not install `training`. No file here imports torch, transformers, Megatron, or vLLM. `env/versions.env.example` leaves model, dataset, adapter, `MEGATRON_BRIDGE_REVISION`, `VLLM_VERSION`, and `TRAINING_CONTAINER_DIGEST` as `UNPINNED`. `vllm/`, `inference/`, and `brev/` are README/spec only. `bench/manifest.v0.1.json` is `DRAFT_DO_NOT_TUNE` with empty splits. SHA `a9904d24bcc1d289a1950fa9d2b978c47cf903b9` does not appear in this tree.

CPU tests run here on system `python3` (no pytest): `tests/historical` 52 OK in 0.335s; `tests.evaluation.test_trace_export` 9 OK in 0.386s. They cover parse, join, redact, split, private output paths, and runner-event chat JSONL. They do not emit Megatron rows.

The 35-task bench freeze is not in this checkout. `mrhinkle/mini-gibson` PR 14 is OPEN at `2da3221e210a53d3365f5f4c2314992f6e9e404a`. The pulls reviews list was empty; commit status was `success` (CodeRabbit).

## Upstream scripts that are not in this tree

`The-AIE/the-gibson` PR 416 merged 2026-10-09 as `07d3749c1a2b3dac3339ef9c43812ea80afdf01e`. It adds `mini-gibson/env/setup-brev.sh`, `verify-env.sh`, `inference/serve-vllm.sh`, and `inference/smoke-test.py`. Setup exits if `VLLM_VERSION` is `UNPINNED`, then `pip install vllm==$VLLM_VERSION`. Verify exits if any required pin is `UNPINNED`, then prints a receipt. Serve runs only `$ROOT/.venv/bin/vllm serve` with `--revision` and `--served-model-name nemotron-base`. Smoke checks `/v1/models` and that a temperature-0 completion contains `MINI_GIBSON_OK`. Those scripts have no tool-call parser, no second model name, and no LoRA flag. None of the four files exist in this worktree.

## Official recipes (public source, not executed here)

Two different NVIDIA paths exist. Neither consumes this repo's JSONL.

Cookbook, Nemotron commit `ccbea41e1ccb8a9bda9169ca83f19d18e39b9cdc` (2026-08-11), directory `usage-cookbook/Nemotron-3.5-Lightning/lora-text2sql/nemo-megatron-bridge/`:

1. `dataprep.py` builds BIRD SQL `training.jsonl`. `BaseSFTDataset` applies the tokenizer chat template (`enable_thinking` for ids containing `nemotron-3`), writes `input`, `output`, `text=input+output`, and `length` from `AutoTokenizer`, and drops rows longer than `max_seq_len`. The notebook sets `max_seq_len=2048`.
2. `convert.py` calls `AutoBridge.import_ckpt` (CPU, bf16) to a Megatron `torch_dist` checkpoint.
3. `torchrun train.py` calls `finetune` on `megatron.bridge.recipes.nemotronh.nemotron_3_5_nano_peft_config("lora")`, then overwrites `hf_model_id` and the tokenizer path. On Megatron-Bridge `main` at fetch (`76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc`, 2026-10-16T00:12:07Z) that function lives in `nemotron_3_nano.py` and its default tokenizer id is the Nano checkpoint. Whether `hf_model_id` replaces the Nano architecture is unverified. `DRY_RUN=1` still imports Megatron.
4. Export is `torchrun --nproc-per-node=1 /opt/Megatron-Bridge/examples/peft/merge_lora.py --lora-checkpoint … --hf-model-path … --output … --cpu`. The notebook then serves that merged directory with vLLM `LLM(model=merge_output_dir)`. One full checkpoint, not a PEFT module.
5. Published container string: `nvcr.io/nvidian/nemo:26.08`. Pullability was not checked. The host is not `nvcr.io/nvidia`.
6. Notebook hardware table, measured by NVIDIA on 80GB H100s for one Text2SQL epoch: 1 GPU ~79 GB / ~60 min (single MTP head), 2 ~51 GB / ~34 min, 4 ~35 GB / ~18 min, 8 ~27 GB / ~8 min, plus ~130 GB disk. This audit did not reproduce that table.

Megatron-Bridge Lightning doc on the same `76cf8ca` (`docs/models/nemotron/nemotron3.5-lightning.md`):

- Verified import/export of the base checkpoint uses HF revision `b3caaabed0263651a17dc1f2d4ce97e794f76c44` and reports a bitwise round-trip (6,513 tensors). That revision is the weight pin in NVIDIA's verification. `a9904d24bcc1d289a1950fa9d2b978c47cf903b9` is a different commit; public history shows it on `tokenizer_config.json`. Use it only as the tokenizer-analysis pin.
- Verified LoRA command name: `nemotron_3_5_lightning_peft_config`, `--mode lora`, packed OpenMathInstruct-2, seq 4096, rank 32, alpha 32, 100 steps. Hardware in that card: 1×8 H100, or 2×4 GB200. The recipes package listing on that `main` has no `lightning` Python module (`nemotron_3_nano.py`, super, ultra only). The `train.sh` name is documented; resolving it was not executed. Use the doc command verbatim. It trains OpenMath, not Mini Gibson JSONL.
- Verified seq-32768 run on that card is full SFT (`nemotron_3_5_lightning_sft_config`), 4×8 H100 or 2×4 GB200. The same card says the two-node H100 layout OOMs at iteration 2. That is not a LoRA result.
- Nemotron SFT doc (`docs.nvidia.com/nemotron` Lightning SFT) states role-based assistant-only loss and per-token loss for the packed OpenMath recipe at seq 4096. This audit did not read the mask implementation. Our records do not carry that mask.

vLLM base serve, day-0 post (2026-08-10): image `vllm/vllm-openai:v0.27.1`, model `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`, 1× H100, with Mamba/MoE backends, `--reasoning-parser nemotron_v3`, `--tool-call-parser qwen3_coder`, `--enable-auto-tool-choice`. Recipes page also says "0.27.1 or newer" and names image tag `v0.28.0`, plus 1× DGX Spark and 1× DGX Station. A Spark measurement there used a nightly. Those combinations are unverified against each other and against container `26.08`. The day-0 command has no `--enable-lora`. Generic vLLM LoRA (`--lora-modules name=path`, model id appears in `/v1/models`) is documented for models that implement `SupportsLoRA` and for PEFT directories. A later vLLM change demonstrates LoRA on Nemotron 3 Nano and Super, which are other checkpoints.

## Missing executable steps

From a train-v7 window to a distinct served model, nothing in this repo or in the cited recipes runs the whole chain:

1. Render `messages`, including `tool` and `tool_calls`, with the Lightning chat template and `enable_thinking`. No local code does this. The cookbook template path is system+user in, one completion out.
2. Set the supervised span to assistant tokens only, using the model tokenizer. Char/4 cannot place that span. Tool tokens are a separate role; the packed OpenMath recipe's role mask was not shown to accept this schema.
3. Decide length against a real tokenizer. Cookbook drops rows over 2048. Verified Lightning LoRA packs at 4096. A window whose char/4 count is near 32768 is a different problem than either recipe, and the verified 32768 path is full SFT on the large shapes above.
4. Emit `training.jsonl` with `input`/`output`/`text`/`length`, or the packed dataset that `nemotron_3_5_lightning_peft_config` actually reads. Pointing our JSONL at either loader is unsupported.
5. Import HF weights at `b3caaab…` with the pinned Megatron-Bridge SHA. `convert.py` records no SHA.
6. Launch LoRA only from a recipe whose architecture is Lightning at that SHA. The cookbook import of the Nano PEFT function is an unverified pairing.
7. Export. The only custom-data export found merges the adapter into a full HF checkpoint. The verified LoRA save is described as a 12-file adapter checkpoint, not as `adapter_config.json` plus `adapter_model.safetensors`.
8. Serve. Merged HF matches the cookbook vLLM call (one model directory). Distinct ids `nemotron-base` and `mini-gibson` are names in `vllm/README.md` only. PR 416 smoke covers the base completion string only. Structured tool call, agent connect, and GibsonEnv smoke from `inference/README.md` have no script and no receipt.

## Adapter versus merged weights

Official custom inference loads the merged HF directory. That artifact is a full model. It is not a vLLM LoRA module. Loading the Megatron adapter directory with `--enable-lora` is unverified for NemotronH Lightning: no cited doc shows a PEFT-folder export, and the Lightning day-0 serve flags omit LoRA. A coder should treat merged-weight serving as the only documented inference path until a pinned Megatron-Bridge revision documents a PEFT export and a pinned vLLM build documents `SupportsLoRA` for this architecture.

## Three layers

| Layer | State on 2026-10-15 |
| --- | --- |
| Doc scaffolding | `docs/training-plan.md`, `docs/brev-plan.md`, `docs/weekend-runbook.md`, `vllm/README.md`, `inference/README.md`, both `versions.env.example` files. Pins are `UNPINNED`. |
| Tested runtime | CPU unit tests above. NVIDIA's published import/export and OpenMath LoRA cards are their measurements, on their data. |
| Measured inference | No Mini Gibson base, merged, or adapter serve receipt in this repo. |

## Proposed coder lane (new files only)

Leave `training/historical/extract.py`, `training/dataset/schema.json`, `STATS.md`, and the data-spec docs to the other lane.

1. Add `training/megatron/prepare.py` and `tests/historical/test_megatron_prepare.py`. Input is one schema-valid window. Output is a cookbook row or a structured skip when the template cannot render `tool_calls`. Length comes from an injected tokenizer. Record the assistant span and assert system, user, and tool text sit outside it. Default max length 2048, matching the cookbook cell; do not clip a long window into a supervised row. Tests must not open `~/gibson-traces` or download weights.
2. Port the four PR 416 scripts to `env/setup-brev.sh`, `env/verify-env.sh`, `inference/serve-vllm.sh`, `inference/smoke-test.py`. Keep the fail-closed pin checks. Do not commit `versions.env` or tokens.
3. Keep laptop `pyproject.toml` free of torch, Megatron, and vLLM. The training container holds those.
4. In `env/versions.env.example`, add the candidate comments below and leave every value `UNPINNED` until Mark chooses.
5. Do not add a trainer. Call the upstream recipe inside the authorized container.
6. Serve the base with the day-0 flag set only after the vLLM image is chosen. Serve a merged export as its own model directory. Do not add `--enable-lora` against a Megatron adapter directory.

Candidate pins, not a verified combined stack:

- Model id: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`
- Weight revision from the Megatron-Bridge verification card: `b3caaabed0263651a17dc1f2d4ce97e794f76c44`
- Tokenizer-analysis revision only: `a9904d24bcc1d289a1950fa9d2b978c47cf903b9`
- Cookbook files last changed in Nemotron `ccbea41e1ccb8a9bda9169ca83f19d18e39b9cdc`. Repo `main` at fetch was `a8b5a501b742ddd6de66743a2d0c74932fec76b4` and is not a pin.
- Megatron-Bridge doc SHA at fetch: `76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc`. Pin a SHA only after the Lightning recipe name resolves there.
- vLLM image candidates, mutually unverified: `vllm/vllm-openai:v0.27.1` (day-0 command) and tag `v0.28.0` (recipes page).
- Training image string as published: `nvcr.io/nvidian/nemo:26.08` (pull unverified).

## No-spend test plan

Re-run the two unittest commands above. Add the prepare tests with a fake tokenizer. Do not run `convert.py`, `train.py`, Docker, `vllm`, or a weight download on the laptop. `DRY_RUN=1` is not a laptop test; it imports Megatron.

## GPU plan (authorization gate)

Stop until Mark names one published hardware profile and authorizes the weight download and GPU time. Do not pick a Brev shape or a price in this lane.

Published options, all Mark's choice: cookbook 1–8× H100 80GB; verified LoRA 8× H100 or 8× GB200 at seq 4096 on OpenMath; verified 32768 full SFT on 32× H100 or 8× GB200; day-0 base inference 1× H100; recipes page also lists 1× DGX Spark and 1× DGX Station. Model card also lists 1× A100 80GB for single-GPU deployment. Prerequisites for any of these: NVIDIA driver visible to `nvidia-smi`, the chosen container actually pulled, on the order of 130 GB free for the cookbook's download plus convert plus merged export, and `HF_TOKEN` injected at runtime.

After that authorization, inside the container: run the published CPU import next to Megatron-Bridge entry `nemotron-3-5-lightning-hf-to-megatron-cpu` at the pinned SHA; run `prepare.py` on a copy of the private JSONL and review real token lengths before any training; smoke the chosen recipe with a small step cap; export with the cookbook `merge_lora.py --cpu` command; serve the merged directory and the base with the pinned vLLM command as two process configs. Keep NVIDIA's OpenMath loss numbers out of the Mini Gibson receipt.
