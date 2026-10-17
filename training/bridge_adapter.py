"""Convert exported HF-style labels into Megatron batches without retokenizing.

The input cap counts unshifted IDs. An input of N tokens yields N - 1 next-token
targets. This module imports neither torch nor Megatron until tensor collation
is explicitly requested. A successful conversion is not a trainer-loader test.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

IGNORE_INDEX = -100


def _integer(value: Any, name: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} must be an integer in the configured range")
    return value


def _arrays(record: Mapping[str, Any], *, vocab_size: int, max_input_tokens: int) -> tuple[list[int], list[int]]:
    if not isinstance(record, Mapping):
        raise ValueError("record must be a mapping")
    ids, hf_labels = record.get("input_ids"), record.get("labels")
    if not isinstance(ids, list) or not isinstance(hf_labels, list):
        raise ValueError("input_ids and labels must be lists")
    if len(ids) != len(hf_labels):
        raise ValueError("input_ids and labels must have equal lengths")
    if not 2 <= len(ids) <= max_input_tokens:
        raise ValueError("input length must be at least two and no greater than max_input_tokens")
    mask = []
    for token, label in zip(ids, hf_labels):
        _integer(token, "input token", 0, vocab_size - 1)
        if type(label) is not int:
            raise ValueError("label must be an integer")
        if label != IGNORE_INDEX:
            _integer(label, "label token", 0, vocab_size - 1)
            if label != token:
                raise ValueError("a supervised label must equal its unshifted input token")
        mask.append(int(label != IGNORE_INDEX))
    if not any(mask[1:]):
        raise ValueError("record must have a supervised next-token target after shifting")
    return ids.copy(), mask


def collate_records(
    records: list[Mapping[str, Any]],
    *,
    vocab_size: int,
    max_input_tokens: int,
    pad_token_id: int,
    pad_to_length: int | None = None,
) -> dict[str, Any]:
    """Validate, shift once, and pad a batch of exported records using stdlib.

    ``labels`` in the export are unshifted input IDs or -100. Returned Megatron
    labels are valid next-token IDs everywhere; the separate shifted loss_mask
    suppresses context and padding. Default padding extends to the longest batch
    member; an explicit pad_to_length must fit the cap and every shifted row.
    No text is read, no tokenization occurs, and overlong rows are rejected.
    """
    _integer(vocab_size, "vocab_size", 1)
    _integer(max_input_tokens, "max_input_tokens", 2)
    _integer(pad_token_id, "pad_token_id", 0, vocab_size - 1)
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a nonempty list")
    arrays = [_arrays(row, vocab_size=vocab_size, max_input_tokens=max_input_tokens) for row in records]
    width = max(len(ids) - 1 for ids, _ in arrays)
    if pad_to_length is not None:
        width = _integer(pad_to_length, "pad_to_length", width, max_input_tokens)
    batch: dict[str, Any] = {
        "tokens": [], "labels": [], "loss_mask": [], "position_ids": [], "attention_mask": None,
    }
    for ids, mask in arrays:
        padding = width - (len(ids) - 1)
        batch["tokens"].append(ids[:-1] + [pad_token_id] * padding)
        batch["labels"].append(ids[1:] + [pad_token_id] * padding)
        batch["loss_mask"].append(mask[1:] + [0] * padding)
        batch["position_ids"].append(list(range(width)))
    return batch


def collate_torch_records(
    records: list[Mapping[str, Any]],
    *,
    vocab_size: int,
    max_input_tokens: int,
    pad_token_id: int,
    pad_to_length: int | None = None,
) -> dict[str, Any]:
    """Return CPU tensors for an explicitly configured dataset's collate_fn.

    Requires the training container's torch installation. Megatron provider
    construction and actual loader execution remain separate integration gates.
    """
    batch = collate_records(
        records, vocab_size=vocab_size, max_input_tokens=max_input_tokens, pad_token_id=pad_token_id,
        pad_to_length=pad_to_length,
    )
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("tensor collation requires torch in the training container") from error
    return {
        key: None if value is None else torch.tensor(value, dtype=torch.float32 if key == "loss_mask" else torch.long)
        for key, value in batch.items()
    }
