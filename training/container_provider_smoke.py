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
