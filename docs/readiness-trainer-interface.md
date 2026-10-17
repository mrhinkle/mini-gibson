# Readiness: pretokenized exports to Megatron Bridge

The CPU format adapter is implemented and tested. **Actual trainer loader: NOT_RUN.**
No model weights, training run, GPU fit, checkpoint save, adapter export, or serving
result has been verified by this change.

`training.bridge_adapter.collate_records` accepts exported `input_ids` and
unshifted HF-style `labels` (a matching input token ID or `-100`). It validates
the entire batch, shifts once, and defaults to padding to the longest member.
An explicit `pad_to_length` selects a fixed target width, bounded by
`max_input_tokens` and no shorter than any shifted row. It never truncates,
retokenizes, opens data files, or changes the original records. The separate
`collate_torch_records` function imports torch only when explicitly called.

For example, IDs `[10, 11, 12, 13]` with exported labels `[-100, -100, 12, 13]`
become:

| Field | Megatron value |
| --- | --- |
| `tokens` | `[10, 11, 12]` |
| `labels` | `[11, 12, 13]` |
| `loss_mask` | `[0, 1, 1]` |
| `position_ids` | `[0, 1, 2]` |
| `attention_mask` | `None` (causal mask supplied by the model) |

Megatron labels are next-token IDs, including at masked positions. **Do not send
HF `-100` values as Megatron targets.** Padding uses a valid explicit pad token
ID and always has zero loss. A real EOS token may equal the pad token ID; its
supervision follows its original label, not its numeric value.

`max_input_tokens` caps **unshifted exported IDs**, so a candidate 4,096-token
export yields at most 4,095 next-token positions. An exact 4,096-position target
would require up to 4,097 unshifted IDs. Keep this distinction explicit when
setting the model sequence length. The candidate uses `pad_to_length=4096`,
adding loss-free padding to produce exactly 4,096 target slots and position IDs.
That explicit width supplies the fixed shape needed by the candidate's sequence
parallel configuration. Actual runtime alignment still needs a container check.
The adapter does not select an alignment multiple or pack examples together.

## Pinned source contract

Use Megatron Bridge commit
`76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc` and Nemotron cookbook commit
`ccbea41e1ccb8a9bda9169ca83f19d18e39b9cdc` when reproducing this investigation.

- The correct Bridge symbol is
  `from megatron.bridge.recipes.nemotronh import nemotron_3_5_lightning_peft_config`,
  called with `"lora"`. It is [exported from the recipe package](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/recipes/nemotronh/__init__.py#L27-L35)
  and [implemented in the H100 Nano recipe module](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/recipes/nemotronh/h100/nemotron_3_nano.py#L647-L660).
  The pinned [cookbook's `nemotron_3_5_nano_peft_config` import](https://github.com/NVIDIA-NeMo/Nemotron/blob/ccbea41e1ccb8a9bda9169ca83f19d18e39b9cdc/usage-cookbook/Nemotron-3.5-Lightning/lora-text2sql/nemo-megatron-bridge/train.py#L33-L37)
  is absent from that Bridge package's exports. Copying that import unchanged fails.
- `GPTSFTDatasetConfig(dataset_root=...)` reads `training.jsonl` and optional
  `validation.jsonl` / `test.jsonl`. Its ordinary prompt-completion path
  [retokenizes text fields](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/data/datasets/gpt_sft.py#L505-L594).
  The cookbook's `input` / `output` / `text` / `length` rows do not carry an
  arbitrary multi-turn assistant mask. Do not pass this export format directly
  to `GPTSFTDataset`, or assume writing its JSONL proves loader compatibility.
- A custom [DatasetProvider.build_datasets(context)](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/data/base.py#L79-L100)
  is an explicitly supported **deprecated compatibility contract** at this pin.
  [Provider dispatch](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/data/utils.py#L105-L149)
  supplies requested split sample counts and accepts a dataset's own
  [collate_fn](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/data/loaders.py#L401-L414).
  Use explicit separate paths for each split and fail when a requested split
  lacks a path. Do not import the holdout into training.
- The adapter follows the native [one-token shift and padding contract](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/data/datasets/gpt_sft.py#L746-L813).
  The [GPT forward step](https://github.com/NVIDIA-NeMo/Megatron-Bridge/blob/76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc/src/megatron/bridge/training/gpt_step.py#L493-L503)
  accepts `attention_mask=None`. Input text/template masking belongs to the
  exporter; this adapter only preserves its validated token labels.

## Executable container smoke gate (not yet executed)

Run this only in an existing matching NVIDIA training container with the Bridge
checkout at `/opt/Megatron-Bridge` and this repository on `PYTHONPATH`. It imports
the actual pinned recipe/provider, reads only temporary synthetic token files,
and obtains a batch through torch DataLoader. It loads no tokenizer, weights,
checkpoint, real corpus, or model and does not call `finetune`. It is a necessary
loader contract check, not a GPU optimizer-step rehearsal or a checkpoint/resume
serialization test. Keep the provider class at module scope when moving it into
a runnable training script; a function-local class is unsuitable for spawn or
durable config reconstruction.

```python
import json
import subprocess
import tempfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import torch
from megatron.bridge.data.base import DatasetProvider
from megatron.bridge.data.utils import get_dataset_provider
from megatron.bridge.recipes.nemotronh import nemotron_3_5_lightning_peft_config
from megatron.bridge.training.finetune import finetune  # import check only
from megatron.bridge.training.gpt_step import forward_step  # import check only
from training.bridge_adapter import collate_torch_records

assert subprocess.check_output(
    ["git", "-C", "/opt/Megatron-Bridge", "rev-parse", "HEAD"], text=True
).strip() == "76cf8ca3402c3fb28465bcc9ef5fbb58d92181bc"


class ExportRows(torch.utils.data.Dataset):
    def __init__(self, path, count, collate):
        with open(path, encoding="utf-8") as stream:
            self.rows = [json.loads(line) for line in stream if line.strip()]
        if not self.rows:
            raise ValueError("empty requested split")
        self.count, self.collate_fn = count, collate

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        return self.rows[index % len(self.rows)]


@dataclass(kw_only=True)
class SyntheticExportProvider(DatasetProvider):
    train_path: str
    validation_path: str | None
    test_path: str | None

    def build_datasets(self, context):
        collate = partial(
            collate_torch_records, vocab_size=128,
            max_input_tokens=4096, pad_token_id=0, pad_to_length=4096,
        )
        datasets = []
        for path, count in zip(
            (self.train_path, self.validation_path, self.test_path),
            (context.train_samples, context.valid_samples, context.test_samples),
        ):
            if count <= 0:
                datasets.append(None)
            elif path is None:
                raise ValueError("requested split needs an explicit path")
            else:
                datasets.append(ExportRows(path, count, collate))
        return tuple(datasets)


with tempfile.TemporaryDirectory() as directory:
    paths = [Path(directory) / name for name in ("train.jsonl", "valid.jsonl", "test.jsonl")]
    rows = [
        [
            {"input_ids": [10, 11, 12, 13], "labels": [-100, -100, 12, 13]},
            {"input_ids": [20, 21], "labels": [-100, 21]},
        ],
        [{"input_ids": [30, 31], "labels": [-100, 31]}],
        [{"input_ids": [40, 41], "labels": [-100, 41]}],
    ]
    for path, split in zip(paths, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in split))
    cfg = nemotron_3_5_lightning_peft_config("lora")
    cfg.dataset = SyntheticExportProvider(
        train_path=str(paths[0]), validation_path=str(paths[1]), test_path=str(paths[2]),
        num_workers=0, persistent_workers=False,
    )
    provider = get_dataset_provider(cfg.dataset)
    train, valid, test = provider([3, 2, 1], config=cfg.dataset)
    assert (len(train), len(valid), len(test)) == (3, 2, 1)
    loader = torch.utils.data.DataLoader(
        train, batch_size=2, num_workers=0, collate_fn=train.collate_fn,
    )
    batch = next(iter(loader))
    assert batch["tokens"].shape == batch["labels"].shape == (2, 4096)
    assert batch["loss_mask"].shape == batch["position_ids"].shape == (2, 4096)
    assert batch["tokens"][:, :3].tolist() == [[10, 11, 12], [20, 0, 0]]
    assert batch["labels"][:, :3].tolist() == [[11, 12, 13], [21, 0, 0]]
    assert batch["loss_mask"][:, :3].tolist() == [[0, 1, 1], [1, 0, 0]]
    assert batch["position_ids"].tolist() == [list(range(4096))] * 2
    assert torch.all(batch["tokens"][:, 3:] == 0)
    assert torch.all(batch["labels"][:, 3:] == 0)
    assert torch.all(batch["loss_mask"][:, 3:] == 0)
    assert batch["tokens"].dtype == batch["labels"].dtype == torch.long
    assert batch["loss_mask"].dtype == torch.float32
    assert batch["attention_mask"] is None
    assert torch.all(batch["labels"] >= 0)
    print("PINNED_PROVIDER_SYNTHETIC_BATCH_PASS")
```

This prints no PASS until every assertion executes. Preserve the container/image
identity, exact Bridge SHA and stdout when it is run. If imports or assertions
fail, retain **trainer loader NOT_RUN/FAILED** and resolve that failure before
starting training. The cookbook's container string is not evidence that an image
is available or that this adapter ran inside it.

After this gate, the separate rehearsal still must exercise the official training
setup/iterator, model-specific sequence alignment, a finite-loss optimizer step,
checkpoint save/resume, export, and serving. The supported training call is
`finetune(config=cfg, forward_step_func=forward_step)` and requires a pretrained
checkpoint or checkpoint load; it is intentionally absent from the smoke test.
