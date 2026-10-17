"""Private, local-only exact-token transcript-SFT preparation; no training."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

MODEL = "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16"
REVISION = "a9904d24bcc1d289a1950fa9d2b978c47cf903b9"
PINS = {
    "tokenizer.json": "623c34567aebb18582765289fbe23d901c62704d6518d71866e0e58db892b5b7",
    "tokenizer_config.json": "10f93eabcb9b1602fbb991d6308e787ce1df28ee9cd7a1c6d1e8c3f338b957bc",
    "special_tokens_map.json": "e9435fefd6d838fd9fcbbc44b97a8e3ff322be7f6dfb7e4fd2468586574bb52b",
    "chat_template.jinja": "58933db77d3099b4f78c55a38347a72e1ea05b97d6bd8f38775303dc0194e0a9",
    "config.json": "a3827a0f5e311547b40943dc081e3ff2f8a277466e8c1a3df2291e8db8a7617c",
}
VERSIONS = {"transformers": "5.20.0", "tokenizers": "0.23.3", "jinja2": "3.1.6"}
OPTIONS = {"enable_thinking": False, "truncate_history_thinking": False, "add_generation_prompt": False}
COLLISION = re.compile(r"<\|[^<>]*\|>|</?think>|</?s>|<unk>|</(?:parameter|function|tool_call|tool_response)\s*>|<(?:tool_call|tool_response)>")


class Rejected(ValueError):
    """Only fixed diagnostic codes, never source content, may be reported."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def transcript_json(value):
    # Parameter order affects native rendering; preserve the order used for IDs.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_rows(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
    except (ValueError, OSError):
        raise Rejected("input_jsonl_invalid") from None
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise Rejected("input_rows_invalid")
    return rows


def source_key(row):
    if not isinstance(row.get("repo"), str) or type(row.get("pr")) is not int or row["pr"] <= 0:
        raise Rejected("source_key_invalid")
    return row["repo"].rsplit("/", 1)[-1].lower(), row["pr"]


def session_id(row):
    value = row.get("episode_id")
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]+-w\d+", value):
        raise Rejected("source_episode_invalid")
    return value.rsplit("-w", 1)[0]


def issues(row):
    values = row.get("issues", [])
    if not isinstance(values, list):
        raise Rejected("source_issues_invalid")
    return {n for n in [row.get("issue"), row.get("issue_number"), *values] if type(n) is int and n > 0}


def groups(messages):
    """Partition tail into user/system prefix + assistant/ordered tool block."""
    result, pending, index = [], [], 2
    while index < len(messages):
        message = messages[index]
        pending.append(index)
        index += 1
        if message.get("role") in {"user", "system"}:
            continue
        if message.get("role") == "assistant" and message.get("tool_calls"):
            while index < len(messages) and messages[index].get("role") == "tool":
                pending.append(index)
                index += 1
        result.append(pending)
        pending = []
    if pending:
        result.append(pending)
    return result


def normalized(messages, normalizations=None):
    output = copy.deepcopy(messages)
    events = []
    # Native tool-response rendering omits IDs: normalize complete parallel
    # batches to call order, without moving anything across another message.
    for index, message in enumerate(output):
        calls = message.get("tool_calls", [])
        if message.get("role") != "assistant" or not calls:
            continue
        if not isinstance(calls, list) or any(not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"] for c in calls):
            raise Rejected("tool_call_shape_invalid")
        identities = [c["id"] for c in calls]
        if len(set(identities)) != len(identities):
            raise Rejected("duplicate_or_invalid_call_id")
        end = index + 1
        while end < len(output) and output[end].get("role") == "tool":
            end += 1
        response_ids = [m.get("tool_call_id") for m in output[index + 1:end]]
        if any(not isinstance(identity, str) or not identity for identity in response_ids):
            raise Rejected("invalid_response_id")
        if len(response_ids) != len(set(response_ids)):
            raise Rejected("duplicate_tool_response")
        if len(response_ids) != len(identities) or set(response_ids) != set(identities):
            raise Rejected("incomplete_or_orphan_tool_batch")
        if response_ids != identities:
            by_id = {m["tool_call_id"]: (m, i) for i, m in enumerate(output[index + 1:end], index + 1)}
            ordered = [by_id[identity] for identity in identities]
            rendered_indices = [i for _, i in ordered]
            output[index + 1:end] = [m for m, _ in ordered]
            events.append({"assistant_source_index": index, "arrival_source_indices": list(range(index + 1, end)), "rendered_source_indices": rendered_indices, "batch_responses": len(ordered), "responses_moved": sum(a != b for a, b in zip(range(index + 1, end), rendered_indices))})
    seen, returned, pending = set(), set(), []
    for message in output:
        if COLLISION.search(canonical(message)):
            raise Rejected("reserved_delimiter_collision")
        role = message.get("role")
        if role not in {"system", "user", "assistant", "tool"} or not (isinstance(message.get("content"), str) or (role == "assistant" and message.get("content") is None)):
            raise Rejected("message_shape_invalid")
        if role != "tool" and pending:
            raise Rejected("unanswered_or_out_of_order_call")
        if role == "tool":
            identity = message.get("tool_call_id")
            if not isinstance(identity, str) or not identity:
                raise Rejected("invalid_response_id")
            if identity in returned:
                raise Rejected("duplicate_tool_response")
            if not pending or identity != pending.pop(0):
                raise Rejected("orphan_or_out_of_order_response")
            returned.add(identity)
        calls = message.get("tool_calls", [])
        if not isinstance(calls, list) or (calls and role != "assistant"):
            raise Rejected("tool_call_shape_invalid")
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                raise Rejected("tool_call_shape_invalid")
            identity, function = call.get("id"), call["function"]
            if not isinstance(identity, str) or not identity or identity in seen:
                raise Rejected("duplicate_or_invalid_call_id")
            if not isinstance(function.get("name"), str) or not function["name"] or re.search(r"[<>\s]", function["name"]):
                raise Rejected("tool_name_invalid")
            raw = function.get("arguments")
            try:
                if not isinstance(raw, str):
                    raise ValueError
                def object_pairs(pairs):
                    value = {}
                    for key, item in pairs:
                        if key in value:
                            raise ValueError
                        value[key] = item
                    return value
                def invalid_constant(value):
                    raise ValueError
                value = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid_constant)
            except ValueError:
                raise Rejected("malformed_tool_arguments") from None
            if not isinstance(value, dict):
                raise Rejected("nonobject_tool_arguments")
            if COLLISION.search(canonical(value)):
                raise Rejected("reserved_delimiter_collision")
            if any(re.search(r"[<>\s]", key) for key in value):
                raise Rejected("tool_parameter_name_invalid")
            function["arguments"] = value
            seen.add(identity)
            pending.append(identity)
    if pending:
        raise Rejected("unanswered_tool_call")
    if normalizations is not None:
        normalizations.extend(events)
    return output


def instrument(native):
    """Add generation metadata only; assert exact, pinned branch anchors."""
    replacements = [
        ("{{- '<|im_start|>assistant\\n' }}", "{{- '<|im_start|>assistant\\n' }}{% generation %}"),
        ("{{- '<|im_end|>\\n' }}\n        {%- else %}", "{{- '<|im_end|>\\n' }}{% endgeneration %}\n        {%- else %}"),
        ("{{- '<|im_start|>assistant\\n' ~ (content | default('', true) | string | trim) ~ '<|im_end|>\\n' }}", "{{- '<|im_start|>assistant\\n' }}{% generation %}{{- (content | default('', true) | string | trim) ~ '<|im_end|>\\n' }}{% endgeneration %}"),
        ("{{- '<|im_start|>assistant\\n' ~ c ~ '<|im_end|>\\n' }}", "{{- '<|im_start|>assistant\\n' }}{% generation %}{{- c ~ '<|im_end|>\\n' }}{% endgeneration %}"),
        ("{{- '<|im_start|>assistant\\n<|im_end|>\\n' }}", "{{- '<|im_start|>assistant\\n' }}{% generation %}{{- '<|im_end|>\\n' }}{% endgeneration %}"),
    ]
    for old, new in replacements:
        if native.count(old) != 1:
            raise Rejected("template_anchor_mismatch")
        native = native.replace(old, new, 1)
    return native


def verified_tokenizer(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "download-manifest.json").read_text())
    if manifest.get("model") != MODEL or manifest.get("revision") != REVISION:
        raise Rejected("tokenizer_revision_mismatch")
    declared = {item["name"]: item["sha256"] for item in manifest.get("files", [])}
    if declared != PINS or any(digest(directory / name) != sha for name, sha in PINS.items()):
        raise Rejected("tokenizer_artifact_mismatch")
    versions = {name: importlib.metadata.version(name) for name in VERSIONS}
    if versions != VERSIONS:
        raise Rejected("dependency_version_mismatch")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest() != PINS["chat_template.jinja"]:
        raise Rejected("loaded_template_mismatch")
    return tokenizer, versions


class Renderer:
    def __init__(self, tokenizer):
        self.tokenizer, self.native = tokenizer, tokenizer.chat_template
        self.marked = instrument(self.native)

    def __call__(self, messages):
        try:
            native = self.tokenizer.apply_chat_template(messages, chat_template=self.native, tokenize=False, **OPTIONS)
            marked = self.tokenizer.apply_chat_template(messages, chat_template=self.marked, tokenize=False, **OPTIONS)
            ids = self.tokenizer(native, add_special_tokens=False)["input_ids"]
            result = self.tokenizer.apply_chat_template(messages, chat_template=self.marked, return_dict=True, return_assistant_tokens_mask=True, **OPTIONS)
        except Exception:
            raise Rejected("template_render_failure") from None
        mask = result.get("assistant_masks")
        if native != marked or ids != result.get("input_ids"):
            raise Rejected("native_equivalence_failure")
        if not isinstance(mask, list) or len(mask) != len(ids) or any(type(n) is not int or n not in (0, 1) for n in mask) or not any(mask[1:]):
            raise Rejected("assistant_mask_invalid")
        return {"text": native, "input_ids": ids, "labels": [token if selected else -100 for token, selected in zip(ids, mask)], "token_count": len(ids)}


def prepare_records(rows, render, cap):
    if type(cap) is not int or cap < 2:
        raise Rejected("sequence_cap_invalid")
    outputs, ledger, dispositions = [], [], Counter()
    for row in rows:
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) < 2 or any(not isinstance(m, dict) for m in messages) or [m.get("role") for m in messages[:2]] != ["system", "user"]:
            raise Rejected("source_header_invalid")
        partitions = groups(messages)
        normalizations = []
        def dispose(index, status, reason):
            events = [event for event in normalizations if event["assistant_source_index"] in partitions[index]]
            index_map = {a: b for event in events for a, b in zip(event["arrival_source_indices"], event["rendered_source_indices"])}
            ledger.append({"source_episode_id": row["episode_id"], "group_index": index, "message_indices": partitions[index], "rendered_source_indices": [index_map.get(i, i) for i in partitions[index]], "tool_response_normalizations": events, "disposition": status, "reason": reason})
            dispositions[reason] += 1
        try:
            clean = normalized(messages, normalizations)
        except Rejected as error:
            for i in range(len(partitions)):
                dispose(i, "quarantined", str(error))
            continue
        header, current, current_groups, rendered, emitted = clean[:2], [], [], None, 0
        def emit():
            nonlocal current, current_groups, rendered, emitted
            if current:
                item = {key: copy.deepcopy(row[key]) for key in row if key != "messages"}
                item.update(rendered)
                item.update({"messages": header + current, "prepared_id": row["episode_id"] + f"-p{emitted:04d}", "source_episode_id": row["episode_id"], "source_session_id": session_id(row), "source_group_indices": current_groups, "partial_context": bool(row.get("window_index", 0) or current_groups[0] or emitted)})
                outputs.append(item)
                emitted += 1
                current, current_groups, rendered = [], [], None
        for i, indexes in enumerate(partitions):
            group = [clean[index] for index in indexes]
            if not any(m.get("role") == "assistant" and (m.get("tool_calls") or (m.get("content") or "").strip()) for m in group):
                emit()
                dispose(i, "quarantined", "no_assistant_content")
                continue
            candidate = render(header + current + group)
            if candidate["token_count"] > cap and current:
                emit()
                candidate = render(header + group)
            if candidate["token_count"] > cap:
                dispose(i, "quarantined", "oversize_atomic_group")
                continue
            current += group
            current_groups.append(i)
            rendered = candidate
            dispose(i, "kept", "packed")
        emit()
    if not outputs:
        raise Rejected("no_usable_output")
    if len(ledger) != sum(len(groups(row["messages"])) for row in rows):
        raise Rejected("group_conservation_failure")
    return outputs, ledger, dict(dispositions)


def split_check(rows, holdout, universe, benchmark):
    allowed = {source_key(row): issues(row) for row in universe}
    retained = {source_key(row) for row in rows}
    if not retained <= allowed.keys() or any(not issues(row) <= allowed[source_key(row)] for row in rows):
        raise Rejected("outside_training_universe")
    held_prs, held_sessions = {source_key(row) for row in holdout}, {session_id(row) for row in holdout}
    held_issues = {(source_key(row)[0], n) for row in holdout for n in issues(row)}
    retained_issues = {(repo, n) for repo, pr in retained for n in allowed[(repo, pr)]}
    if retained & held_prs or {session_id(row) for row in rows} & held_sessions or retained_issues & held_issues:
        raise Rejected("holdout_key_overlap")
    if retained & {source_key(row) for row in benchmark} or retained_issues & {(source_key(row)[0], n) for row in benchmark for n in issues(row)}:
        raise Rejected("benchmark_key_overlap")
    return [{"repo": repo, "pr": pr, "issues": sorted(allowed[(repo, pr)])} for repo, pr in sorted(retained)]


def write_private(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def run(args):
    output = Path(args.output).resolve()
    source, holdout_path, tokenizer_path = map(lambda p: Path(p).resolve(), (args.source, args.holdout, args.tokenizer))
    inputs = [source, holdout_path, tokenizer_path, Path(args.training_keys).resolve(), Path(args.benchmark_dir).resolve()]
    if os.path.lexists(args.output) or any(output == p or output in p.parents or p in output.parents for p in inputs):
        raise Rejected("output_existing_or_overlapping")
    before = {str(p): digest(p) for p in (source, holdout_path)}
    rows, holdout = load_rows(source), load_rows(holdout_path)
    if len({row.get("episode_id") for row in rows}) != len(rows):
        raise Rejected("duplicate_source_episode")
    for row in rows + holdout:
        source_key(row), session_id(row)
    # Holdout messages are never inspected, normalized, tokenized or used to tune policy.
    holdout = [{key: row[key] for key in ("repo", "pr", "issue", "issues", "episode_id") if key in row} for row in holdout]
    universe = json.loads(Path(args.training_keys).read_text())
    benchmark = [json.loads(p.read_text()) for p in sorted(Path(args.benchmark_dir).glob("*/task.json"))]
    if not isinstance(universe, list) or not universe or not benchmark:
        raise Rejected("contamination_keys_missing")
    split_check(rows, holdout, universe, benchmark)
    tokenizer, versions = verified_tokenizer(tokenizer_path)
    renderer = Renderer(tokenizer)
    outputs, ledger, reasons = prepare_records(rows, renderer, args.max_tokens)
    retained = split_check(outputs, holdout, universe, benchmark)
    after = {str(p): digest(p) for p in (source, holdout_path)}
    if before != after:
        raise Rejected("source_changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + output.name + "-", dir=output.parent))
    os.chmod(staging, 0o700)
    try:
        artifacts = {"train.jsonl": "".join(transcript_json(row) + "\n" for row in outputs), "groups.jsonl": "".join(canonical(row) + "\n" for row in ledger), "retained-keys.json": canonical(retained) + "\n", "chat_template.instrumented.jinja": renderer.marked}
        for name, text in artifacts.items():
            write_private(staging / name, text)
        if before != {str(p): digest(p) for p in (source, holdout_path)}:
            raise Rejected("source_changed")
        manifest = {"format": "private-transcript-sft-v8", "complete": True, "model": MODEL, "revision": REVISION, "sequence_cap": args.max_tokens, "template_options": OPTIONS, "tools_supplied": False, "tokenizer_file_hashes": PINS, "tokenizer_manifest_sha256": digest(tokenizer_path / "download-manifest.json"), "native_template_sha256": PINS["chat_template.jinja"], "instrumented_template_sha256": digest(staging / "chat_template.instrumented.jinja"), "masking": "instrumented-native-equivalent-generation-spans", "versions": versions, "source_hashes_before": before, "source_hashes_after": after, "training_keys_sha256": digest(args.training_keys), "benchmark_key_file_hashes": {str(p): digest(p) for p in sorted(Path(args.benchmark_dir).glob("*/task.json"))}, "artifact_hashes": {name: digest(staging / name) for name in artifacts}, "input_windows": len(rows), "output_windows": len(outputs), "input_groups": len(ledger), "kept_groups": sum(item["disposition"] == "kept" for item in ledger), "quarantined_groups": sum(item["disposition"] == "quarantined" for item in ledger), "disposition_reasons": reasons, "input_messages": sum(len(row["messages"]) for row in rows), "output_messages_with_repeated_headers": sum(len(row["messages"]) for row in outputs), "actual_tokens": sum(row["token_count"] for row in outputs), "max_actual_tokens": max(row["token_count"] for row in outputs), "assistant_target_tokens": sum(sum(label != -100 for label in row["labels"]) for row in outputs), "retained_source_windows": len({row["source_episode_id"] for row in outputs}), "retained_sessions": sorted({row["source_session_id"] for row in outputs}), "retained_prs": len(retained), "retained_repo_windows": dict(Counter(source_key(row)[0] for row in outputs)), "stages": {"prepare": "PASS", "render_native_equivalence": "PASS", "assistant_mask": "PASS", "split_keys": "PASS", **{name: "NO_GO" for name in ("tool_conformance", "megatron_dataset", "gpu", "release", "full_training")}}, "limitations": ["Private operational data; no release authorization.", "Merged session outcomes are provenance, not independent verification of each window.", "Native-equivalent assistant rendering adds native empty thinking markup; observed message content is not rewritten.", "No actual runtime tool schema was supplied; tool conformance is unproven.", "CPU export is not actual Megatron loader or hardware validation.", "Key separation does not establish exhaustive leakage absence."]}
        kept_windows = {item["source_episode_id"] for item in ledger if item["disposition"] == "kept"}
        excluded_windows = {row["episode_id"] for row in rows} - kept_windows
        manifest.update({"excluded_source_windows": len(excluded_windows), "training_universe_prs": len(universe), "kept_group_messages": sum(len(item["message_indices"]) for item in ledger if item["disposition"] == "kept"), "quarantined_group_messages": sum(len(item["message_indices"]) for item in ledger if item["disposition"] == "quarantined"), "source_header_messages": 2 * len(rows), "quarantined_messages_by_reason": dict(Counter({reason: sum(len(item["message_indices"]) for item in ledger if item["reason"] == reason) for reason in reasons if reason != "packed"}))})
        events = [event for item in ledger for event in item["tool_response_normalizations"]]
        kept_events = [event for item in ledger if item["disposition"] == "kept" for event in item["tool_response_normalizations"]]
        manifest["response_order_normalization"] = {"policy": "complete-contiguous-ID-bijection-only; call-order preserved; responses reordered", "validated_batches_normalized": len(events), "validated_responses_moved": sum(e["responses_moved"] for e in events), "retained_batches_normalized": len(kept_events), "retained_responses_moved": sum(e["responses_moved"] for e in kept_events)}
        write_private(staging / "manifest.json", canonical(manifest) + "\n")
        write_private(staging / "COMPLETED.sha256", digest(staging / "manifest.json") + "\n")
        # Exclusive reservation prevents replacing an existing destination, even empty.
        os.mkdir(output, 0o700)
        for path in sorted(staging.iterdir(), key=lambda p: p.name == "COMPLETED.sha256"):
            if path.name == "COMPLETED.sha256" and before != {str(p): digest(p) for p in (source, holdout_path)}:
                raise Rejected("source_changed_before_seal")
            os.rename(path, output / path.name)
        staging.rmdir()
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {key: manifest[key] for key in ("input_windows", "output_windows", "input_groups", "kept_groups", "quarantined_groups", "disposition_reasons", "actual_tokens", "max_actual_tokens", "assistant_target_tokens", "retained_source_windows", "retained_prs", "retained_repo_windows", "artifact_hashes", "stages")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "holdout", "tokenizer", "training-keys", "benchmark-dir", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--max-tokens", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except Exception as error:
        print(canonical({"status": "ERROR", "reason": str(error) if isinstance(error, Rejected) else type(error).__name__}))
        return 1
    print(canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
