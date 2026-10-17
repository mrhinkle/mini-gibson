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

# GPU rehearsal — commands prepared, launch waiting

Date: 2026-10-15. Worktree: `/Users/mrhinkle/Code/mini-gibson-wt/readiness-pipeline-20261015`. This file does not start a GPU, pull weights, read the corpus, or send mail.

Image, hardware, and spend are **UNRESOLVED**. Do not run any container command until Mark names the instance and authorizes the spend. Candidate strings below are public references, not a verified combined stack.

## Pins that are not a stack

- Model id (public): `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`
- Weight revision on the Megatron-Bridge verification card: `b3caaabed0263651a17dc1f2d4ce97e794f76c44`
- `a9904d24bcc1d289a1950fa9d2b978c47cf903b9` is a tokenizer-analysis pin only. It is not the training stack.
- Lightning recipe symbol on the pinned Bridge: `megatron.bridge.recipes.nemotronh.nemotron_3_5_lightning_peft_config` (module `h100/nemotron_3_nano.py`, lines 647–660). The cookbook `train.py` Nano import is incompatible with that Bridge. Do not call it.
- vLLM class `NemotronHForCausalLM` documents `SupportsLoRA` (v0.23.0 API). That does not prove a Megatron adapter is a PEFT export or that the Lightning target modules match. Merged HF weights stay the custom-data serve candidate. Do not pass `--enable-lora` at the Megatron adapter directory.
- Parser flags on the public model card (`--reasoning-parser nemotron_v3`, `--tool-call-parser qwen3_coder`, `--enable-auto-tool-choice`, image `vllm/vllm-openai:v0.27.1`) are not verified together with `nvcr.io/nvidian/nemo:26.08` or with tag `v0.28.0`.

Hardware is Mark's choice, not this lane's: cookbook 1–8× H100 80GB; OpenMath LoRA 8× H100 or 8× GB200; 32768 full SFT 32× H100 or 8× GB200; model-card inference 1× H100 or 1× A100 80GB; DGX Spark / DGX Station only if he picks that page's image.

## Laptop checks that exist now

Corpus stays private. Do not open `~/gibson-traces`, copy JSONL into git, or attach it to a note.

```bash
python3 -m unittest tests.evaluation.test_inference_smoke
python3 -m unittest tests.evaluation.test_trace_export
python3 -m unittest discover -s tests/historical
```

Fixture tool-format smoke (no endpoint, not measured, not scored):

```bash
python3 -m inference.smoke --mode fixture --model MODEL --nonce NONCE \
  --fixture-models models.json --fixture-completion completion.json \
  --output receipt.json
```

Omit `--mode` and the command stays offline. `--mode live` without `--endpoint` exits nonzero and does not connect. A second `--output` to an existing path exits nonzero and does not clobber. Receipt fields that must stay put: `measured_inference` false, fixture `live_inference` false, `model_revision_verified` false, `score` `NOT_SCORED`, `stages.full_training` and `stages.tool_conformance` `NO_GO`.

`training/historical/prepare.py` is a separate exporter. Do not assume its manifest fields and do not point its files at a loader from this runbook.

`training/bridge_adapter.py` is not in this worktree. A separate lane owns that conversion of exporter `input_ids` / HF labels into next-token ids and a shifted `loss_mask`. The NeMo loader was **NOT_RUN**. Do not copy that file here, do not add train flags for it, and do not treat a local conversion as container acceptance.

## After Mark authorizes spend — still no custom-data train command

There is no final training command for the Mini Gibson dataset in this document. Do not invent `--dataset` paths, packing flags, or a step cap on our JSONL. NVIDIA's OpenMath card (`--dataset openmathinstruct2`, `--max_steps 100`) trains OpenMath. Keep those loss numbers out of any Mini Gibson receipt.

Order, each receipt tagged `NOT_SCORED`:

1. Record the image, hardware, Bridge SHA, and weight revision he chose. Repo example pins stay `UNPINNED`.
2. Base import only, of the published base checkpoint, after the container is the one he named. The Megatron-Bridge CPU import entry is `nemotron-3-5-lightning-hf-to-megatron-cpu` with HF revision `b3caaab…`. Confirm the script text in that pinned doc before typing it. This does not load Mini Gibson rows.
3. Run the in-tree exporter on a private copy. Review real token lengths. Stop if the file is absent or its fields are still unsettled.
4. Loader and mask before any optimizer step. Show the pinned Lightning recipe reading that exporter output, and show the assistant-only loss span on those rows. `bridge_adapter.py` is not that proof. Cookbook BIRD rows and OpenMath packs are different datasets. Stop on a mismatch. This gate is **NO_GO** until that probe exists.
5. Ten-step finite-loss smoke only after step 4, by changing the step cap on the command that probe actually accepted. Until that command exists, do not run training. A finite loss on OpenMath is not a Mini Gibson result.
6. Merge an adapter that came from the pinned Lightning recipe into a new HF directory, not the base snapshot. Cookbook notebook `mbridge_lora_cookbook.ipynb` at `ccbea41` uses `torchrun --nproc-per-node=1 /opt/Megatron-Bridge/examples/peft/merge_lora.py --lora-checkpoint … --hf-model-path … --output … --cpu`. That merge is for an adapter this lane has not produced.
7. Serve the merged directory and the base as two process configs. Then, and only then:

```bash
python3 -m inference.smoke --mode live --endpoint http://127.0.0.1:PORT \
  --model SERVED_ID --claimed-revision CLAIMED --timeout 30 --output receipt.json
```

`--claimed-revision` is operator-claimed. `/v1/models` cannot prove it. The receipt must keep `model_revision_verified` false and both stages `NO_GO`. This checks one forced `gibson_smoke` call. It is not GibsonEnv conformance.

Full-data training stays blocked until the protocol freeze and an A/B baseline (`docs/training-plan.md`, `docs/experiment-protocol.md` still draft, weekend runbook Gate 5). The ten-step smoke is not that run.

## Organizer question — draft only, do not send

Ask only if Mark wants it sent. This lane did not send it.

> We have not started a GPU or downloaded weights. Which published hardware profile and container should a Nemotron 3.5 Lightning 30B-A3B BF16 team pin for vLLM serving and for Megatron-Bridge, and is the weight download on the event account? We will wait for that answer plus our own spend approval. We will not send training data.
