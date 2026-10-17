"""CPU-only contract checks for pretokenized export to Megatron batches."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.bridge_adapter import collate_records  # noqa: E402


def batch(rows, **overrides):
    config = {"vocab_size": 100, "max_input_tokens": 8, "pad_token_id": 0}
    return collate_records(rows, **(config | overrides))


class BridgeAdapterTests(unittest.TestCase):
    def test_shifted_targets_and_mask_use_valid_ids(self):
        result = batch([{"input_ids": [10, 11, 12, 13], "labels": [-100, -100, 12, 13]}])
        self.assertEqual(result, {
            "tokens": [[10, 11, 12]], "labels": [[11, 12, 13]],
            "loss_mask": [[0, 1, 1]], "position_ids": [[0, 1, 2]], "attention_mask": None,
        })
        self.assertNotIn(-100, result["labels"][0])

    def test_padding_preserves_real_eos_targets_and_masks_pad(self):
        result = batch([
            {"input_ids": [10, 11, 0, 13], "labels": [-100, 11, 0, 13]},
            {"input_ids": [20, 21], "labels": [-100, 21]},
        ])
        self.assertEqual(result["tokens"], [[10, 11, 0], [20, 0, 0]])
        self.assertEqual(result["labels"], [[11, 0, 13], [21, 0, 0]])
        self.assertEqual(result["loss_mask"], [[1, 1, 1], [1, 0, 0]])
        self.assertEqual(result["position_ids"], [[0, 1, 2], [0, 1, 2]])

    def test_source_and_nested_arrays_are_not_mutated_or_aliased(self):
        rows = [{"input_ids": [10, 11, 12], "labels": [-100, 11, 12], "metadata": {"n": [1]}}]
        saved = copy.deepcopy(rows)
        result = batch(rows)
        result["tokens"][0][0] = 99
        result["labels"][0][0] = 99
        result["loss_mask"][0][0] = 0
        self.assertEqual(rows, saved)

    def test_explicit_padding_sets_fixed_shape_without_changing_supervision(self):
        rows = [
            {"input_ids": [10, 11, 12, 13], "labels": [-100, -100, 12, 13]},
            {"input_ids": [20, 21], "labels": [-100, 21]},
        ]
        result = batch(rows, pad_to_length=8)
        self.assertEqual(result["tokens"], [[10, 11, 12, 0, 0, 0, 0, 0], [20, 0, 0, 0, 0, 0, 0, 0]])
        self.assertEqual(result["labels"], [[11, 12, 13, 0, 0, 0, 0, 0], [21, 0, 0, 0, 0, 0, 0, 0]])
        self.assertEqual(result["loss_mask"], [[0, 1, 1, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0]])
        self.assertEqual(result["position_ids"], [list(range(8)), list(range(8))])
        self.assertEqual(sum(map(sum, result["loss_mask"])), sum(map(sum, batch(rows)["loss_mask"])))
        self.assertEqual(batch(rows, pad_to_length=3), batch(rows))

    def test_invalid_explicit_padding_cannot_truncate_or_exceed_input_cap(self):
        row = {"input_ids": [10, 11, 12, 13], "labels": [-100, -100, 12, 13]}
        for value in [0, 2, 9, True, False, 4.0, "4"]:
            with self.subTest(pad_to_length=value), self.assertRaises(ValueError):
                batch([row], pad_to_length=value)

    def test_input_cap_counts_unshifted_ids_and_never_truncates(self):
        row = {"input_ids": [1, 2, 3], "labels": [-100, 2, 3]}
        self.assertEqual(len(batch([row], max_input_tokens=3)["tokens"][0]), 2)
        with self.assertRaises(ValueError):
            batch([row], max_input_tokens=2)

    def test_missing_mismatched_or_nonlist_arrays_fail(self):
        bad = [{}, {"input_ids": [1, 2]}, {"input_ids": [1, 2], "labels": [2]},
               {"input_ids": (1, 2), "labels": [-100, 2]},
               {"input_ids": [1, 2], "labels": "bad"}, None]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(ValueError):
                batch([row])

    def test_empty_short_or_no_shifted_supervision_fail(self):
        for row in [
            {"input_ids": [], "labels": []}, {"input_ids": [1], "labels": [1]},
            {"input_ids": [1, 2], "labels": [-100, -100]},
            {"input_ids": [1, 2], "labels": [1, -100]},
        ]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                batch([row])
        for rows in [[], None, "rows"]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                batch(rows)

    def test_invalid_ids_labels_and_already_shifted_labels_fail(self):
        for row in [
            {"input_ids": [-100, 2], "labels": [-100, 2]},
            {"input_ids": [1, 100], "labels": [-100, 100]},
            {"input_ids": [1, 2], "labels": [-100, -1]},
            {"input_ids": [1, 2], "labels": [-100, 100]},
            {"input_ids": [1, 2, 3], "labels": [2, 3, -100]},
            {"input_ids": [1, 2], "labels": [-100, 1]},
        ]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                batch([row])

    def test_bool_float_and_string_values_do_not_pass_as_integers(self):
        for bad in [True, False, 2.0, "2", None]:
            for field in ["input_ids", "labels"]:
                row = {"input_ids": [1, 2], "labels": [-100, 2]}
                row[field][1] = bad
                with self.subTest(value=bad, field=field), self.assertRaises(ValueError):
                    batch([row])

    def test_invalid_configuration_fails_before_collation(self):
        row = {"input_ids": [1, 2], "labels": [-100, 2]}
        for overrides in [
            {"vocab_size": 0}, {"vocab_size": True}, {"vocab_size": 100.0},
            {"max_input_tokens": 1}, {"max_input_tokens": True},
            {"pad_token_id": -1}, {"pad_token_id": 100}, {"pad_token_id": False},
        ]:
            with self.subTest(config=overrides), self.assertRaises(ValueError):
                batch([row], **overrides)


if __name__ == "__main__":
    unittest.main()
