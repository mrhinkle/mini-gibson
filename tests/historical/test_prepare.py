"""Synthetic CPU unit checks; fake renderers do not establish model compatibility."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from training.historical import prepare as p  # noqa: E402


def source(messages=None, episode="abc-w00", pr=1, issue=11):
    return {"repo": "test-repo", "pr": pr, "issue": issue, "episode_id": episode,
            "window_index": 0, "messages": messages or [
                {"role": "system", "content": "policy"}, {"role": "user", "content": "task"},
                {"role": "assistant", "content": "answer"}]}


def call(identity="one", arguments='{"command":"echo synthetic"}'):
    return {"role": "assistant", "content": "", "tool_calls": [{"id": identity,
            "type": "function", "function": {"name": "run_command", "arguments": arguments}}]}


def tool(identity="one"):
    return {"role": "tool", "tool_call_id": identity, "content": "synthetic output"}


def fake_render(messages):
    # Each synthetic message costs its text length plus four; no real tokenizer claim.
    size = sum(len(m.get("content") or "") + 4 + (10 if m.get("tool_calls") else 0) for m in messages)
    return {"text": "synthetic", "token_count": size, "input_ids": [1] * size,
            "labels": [-100] * (size - 1) + [1]}


class PrepareTests(unittest.TestCase):
    def test_argument_objects_and_source_immutability(self):
        messages = source()["messages"][:2] + [call(), tool()]
        saved = copy.deepcopy(messages)
        clean = p.normalized(messages)
        self.assertEqual(clean[-2]["tool_calls"][0]["function"]["arguments"], {"command": "echo synthetic"})
        self.assertEqual(messages, saved)

    def test_malformed_scalar_trailing_and_duplicate_argument_keys_rejected(self):
        for raw in ['{"x":}', '"scalar"', '[]', 'null', '{} junk', '{"x":1,"x":2}', '{"x":NaN}']:
            with self.subTest(raw=raw), self.assertRaises(p.Rejected):
                p.normalized(source()["messages"][:2] + [call(arguments=raw), tool()])

    def test_all_closure_failures_reject_window(self):
        variants = [
            [call()], [tool()], [call(), tool(), tool()],
            [call(), tool("wrong")], [call(), {"role": "user", "content": "interrupted"}, tool()],
            [call(), tool(), call(), tool()], [call(), {"role": "tool", "tool_call_id": [], "content": "x"}],
        ]
        for suffix in variants:
            with self.subTest(suffix=suffix), self.assertRaises(p.Rejected):
                p.normalized(source()["messages"][:2] + suffix)

    def test_parallel_responses_normalize_only_complete_id_bijections(self):
        assistant = call()
        assistant["tool_calls"].extend(call("two")["tool_calls"])
        messages = source()["messages"][:2] + [assistant, tool(), tool("two")]
        self.assertEqual(p.groups(messages), [[2, 3, 4]])
        p.normalized(messages)
        first, second = tool(), tool("two")
        first["content"], second["content"] = "result for one", "result for two"
        permuted = messages[:3] + [second, first]
        saved, audit = copy.deepcopy(permuted), []
        clean = p.normalized(permuted, audit)
        self.assertEqual([(m["tool_call_id"], m["content"]) for m in clean[3:]],
                         [("one", "result for one"), ("two", "result for two")])
        self.assertEqual(permuted, saved)
        self.assertEqual(audit[0]["rendered_source_indices"], [4, 3])
        self.assertEqual(audit[0]["responses_moved"], 2)
        out, ledger, _ = p.prepare_records([source(permuted)], fake_render, 1000)
        self.assertEqual(ledger[0]["rendered_source_indices"], [2, 4, 3])
        self.assertEqual(ledger[0]["tool_response_normalizations"], audit)
        for middle in [{"role": "user", "content": "boundary"}, {"role": "assistant", "content": "boundary"}]:
            with self.subTest(middle=middle), self.assertRaises(p.Rejected):
                p.normalized(messages[:3] + [second, middle, first])

    def test_raw_role_and_parameter_delimiters_are_quarantined(self):
        for token in ["<|im_start|>", "<think>", "</parameter>", "</tool_response>"]:
            messages = source()["messages"][:2] + [call(arguments=json.dumps({"x": token})), tool()]
            with self.subTest(token=token), self.assertRaises(p.Rejected):
                p.normalized(messages)
        with self.assertRaises(p.Rejected):
            p.normalized(source()["messages"][:2] + [call(arguments='{"x":"\\u003c/parameter>"}'), tool()])

    def test_exact_cap_and_oversize_groups_conserve_input(self):
        row = source()
        exact = fake_render(row["messages"])["token_count"]
        out, ledger, reasons = p.prepare_records([row], fake_render, exact)
        self.assertEqual(out[0]["token_count"], exact)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(reasons, {"packed": 1})
        with self.assertRaisesRegex(p.Rejected, "no_usable_output"):
            p.prepare_records([row], fake_render, exact - 1)
        long = source()["messages"][:2] + [{"role": "assistant", "content": "x" * 100}, {"role": "assistant", "content": "ok"}]
        out, ledger, reasons = p.prepare_records([source(long)], fake_render, exact)
        self.assertEqual(reasons, {"oversize_atomic_group": 1, "packed": 1})
        self.assertTrue(out[0]["partial_context"])
        self.assertEqual([item["group_index"] for item in ledger], [0, 1])

    def test_continuations_repeat_headers_and_keep_later_user_order(self):
        header = source()["messages"][:2]
        messages = header + [{"role": "assistant", "content": "first"},
            {"role": "user", "content": "next"}, {"role": "assistant", "content": "second"}]
        cap = fake_render(header + messages[3:])["token_count"]
        outputs, ledger, _ = p.prepare_records([source(messages)], fake_render, cap)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[1]["messages"], header + messages[3:])
        self.assertFalse(outputs[0]["partial_context"])
        self.assertTrue(outputs[1]["partial_context"])
        self.assertNotEqual(outputs[0]["prepared_id"], outputs[1]["prepared_id"])
        self.assertEqual([x["disposition"] for x in ledger], ["kept", "kept"])

    def test_structural_quarantine_is_whole_window(self):
        bad = source(source()["messages"] + [call(arguments="broken"), tool()])
        good = source(episode="ghi-w00", pr=3, issue=13)
        outputs, ledger, reasons = p.prepare_records([bad, good], fake_render, 1000)
        self.assertEqual(len(outputs), 1)
        self.assertEqual(reasons, {"malformed_tool_arguments": 2, "packed": 1})
        self.assertEqual(len([item for item in ledger if item["disposition"] == "quarantined"]), 2)

    def test_empty_or_no_assistant_content_refused(self):
        for rows in [[], [source(source()["messages"][:2])],
                     [source(source()["messages"][:2] + [{"role": "assistant", "content": " "}])]]:
            with self.subTest(rows=rows), self.assertRaises(p.Rejected):
                p.prepare_records(rows, fake_render, 1000)

    def test_training_keys_are_allow_universe_not_denylist(self):
        train, held = source(), source(episode="def-w00", pr=2, issue=12)
        universe = [{"repo": "test-repo", "pr": 1, "issues": [11]}]
        self.assertEqual(p.split_check([train], [held], universe, [{"repo": "test-repo", "pr": 3, "issues": [13]}]), universe)
        for hold, bench, allowed in [([train], [], universe), ([held], [train], universe),
                                     ([held], [], []), ([held], [{"repo": "test-repo", "pr": 3, "issues": [11]}], universe)]:
            with self.subTest(hold=hold, bench=bench), self.assertRaises(p.Rejected):
                p.split_check([train], hold, allowed, bench)

    def test_wrong_or_tampered_tokenizer_manifest_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "download-manifest.json").write_text('{"model":"wrong"}')
            with self.assertRaisesRegex(p.Rejected, "revision"):
                p.verified_tokenizer(root)
            for name in p.PINS:
                (root / name).write_text("tampered")
            manifest = {"model": p.MODEL, "revision": p.REVISION,
                        "files": [{"name": n, "sha256": s} for n, s in p.PINS.items()]}
            (root / "download-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(p.Rejected, "artifact"):
                p.verified_tokenizer(root)

    def test_template_anchor_or_mask_failure_is_hard_error(self):
        with self.assertRaises(p.Rejected):
            p.instrument("unknown template")
        class Fake:
            def apply_chat_template(self, messages, **kwargs):
                if kwargs.get("tokenize") is False:
                    return "same"
                return {"input_ids": [1, 2], "assistant_masks": [0, 0]}
            def __call__(self, text, **kwargs):
                return {"input_ids": [1, 2]}
        renderer = object.__new__(p.Renderer)
        renderer.tokenizer, renderer.native, renderer.marked = Fake(), "native", "marked"
        with self.assertRaisesRegex(p.Rejected, "mask"):
            renderer(source()["messages"])
        class WrongIds(Fake):
            def __call__(self, text, **kwargs):
                return {"input_ids": [9, 9]}
        renderer.tokenizer = WrongIds()
        with self.assertRaisesRegex(p.Rejected, "equivalence"):
            renderer(source()["messages"])

    def test_run_private_deterministic_seal_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src, held, keys = [root / name for name in ("train.jsonl", "holdout.jsonl", "keys.json")]
            assistant = call(arguments='{"z":1,"a":2}')
            assistant["tool_calls"].extend(call("two")["tool_calls"])
            src.write_text(json.dumps(source(source()["messages"][:2] + [assistant, tool("two"), tool()])) + "\n")
            held.write_text(json.dumps(source(episode="def-w00", pr=2, issue=12)) + "\n")
            keys.write_text(json.dumps([{"repo": "test-repo", "pr": 1, "issues": [11]}]))
            tokenizer, bench = root / "tokenizer", root / "bench"
            tokenizer.mkdir(); (tokenizer / "download-manifest.json").write_text("{}")
            (bench / "task").mkdir(parents=True)
            (bench / "task" / "task.json").write_text(json.dumps({"repo": "test-repo", "pr": 3, "issues": [13]}))
            args = Namespace(source=str(src), holdout=str(held), tokenizer=str(tokenizer),
                training_keys=str(keys), benchmark_dir=str(bench), output=str(root / "out1"), max_tokens=1000)
            before = p.digest(src), p.digest(held)
            class FakeRenderer:
                marked = "synthetic-generation-metadata"
                def __init__(self, tokenizer): pass
                def __call__(self, messages): return fake_render(messages)
            with patch.object(p, "verified_tokenizer", return_value=(None, {"fake": "unit-only"})), patch.object(p, "Renderer", FakeRenderer):
                first = p.run(args)
                with self.assertRaises(p.Rejected): p.run(args)
                args.output = str(root / "out2")
                second = p.run(args)
                self.assertEqual(first["artifact_hashes"], second["artifact_hashes"])
                args.output = str(src)
                with self.assertRaises(p.Rejected): p.run(args)
            output = root / "out1"
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o700)
            self.assertTrue(all(os.stat(path).st_mode & 0o777 == 0o600 for path in output.iterdir()))
            self.assertEqual((output / "COMPLETED.sha256").read_text().strip(), p.digest(output / "manifest.json"))
            prepared = json.loads((output / "train.jsonl").read_text())
            self.assertEqual(list(prepared["messages"][2]["tool_calls"][0]["function"]["arguments"]), ["z", "a"])
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["response_order_normalization"]["retained_batches_normalized"], 1)
            self.assertEqual(manifest["response_order_normalization"]["retained_responses_moved"], 2)
            self.assertEqual(before, (p.digest(src), p.digest(held)))
            self.assertEqual(first["stages"]["megatron_dataset"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
