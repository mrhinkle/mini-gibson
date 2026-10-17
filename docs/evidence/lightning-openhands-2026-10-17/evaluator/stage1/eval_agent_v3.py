#!/usr/bin/env python3
"""Small deterministic tool-use A/B harness for synthetic Mini-Gibson DEV issues."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import torch
import transformers
from peft import PeftModel, get_peft_model_state_dict
from safetensors import safe_open
from transformers import AutoModelForCausalLM, AutoTokenizer

from agent_contract import (
    MODEL,
    MODEL_REVISION,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_SHA256,
    TOOLS,
    TOOLS_SHA256,
)
from observability import export_observability

HARNESS_VERSION = 7
MAX_TURNS = 10
MAX_NEW_TOKENS = 512
SOURCE_ADAPTER_WEIGHTS_SHA256 = "7acf4381661099918c3d41c8196f919dbebd6e496831e1af5c59de6bf857a612"
IGNORED_SNAPSHOT_PARTS = frozenset({"__pycache__", ".pytest_cache"})
TASKS = {
    "fresh-fix-clamp": {"verify": "python3 -m unittest -q", "allowed_changes": ["bounds.py"]},
    "fresh-fix-factorial": {"verify": "python3 -m unittest -q", "allowed_changes": ["math_helpers.py"]},
    "fresh-fix-greeting": {"verify": "python3 -m unittest -q", "allowed_changes": ["greeter.py"]},
    "fresh-fix-slugify": {"verify": "python3 -m unittest -q", "allowed_changes": ["text_utils.py"]},
    "fresh-a-apportion-cents": {"verify": "python3 -m unittest -q", "allowed_changes": ["allocation.py"]},
    "fresh-a-chunked": {"verify": "python3 -m unittest -q", "allowed_changes": ["chunks.py"]},
    "fresh-a-inventory-ledger": {"verify": "python3 -m unittest -q", "allowed_changes": ["ledger.py"]},
    "fresh-a-merge-spans": {"verify": "python3 -m unittest -q", "allowed_changes": ["spans.py"]},
    "fresh-a-moving-average": {"verify": "python3 -m unittest -q", "allowed_changes": ["metrics.py"]},
    "fresh-a-parse-duration": {"verify": "python3 -m unittest -q", "allowed_changes": ["duration.py"]},
    "fresh-a-query-multimap": {"verify": "python3 -m unittest -q", "allowed_changes": ["query.py"]},
    "fresh-a-redact-token": {"verify": "python3 -m unittest -q", "allowed_changes": ["redact.py"]},
    "fresh-a-ring-cursor": {"verify": "python3 -m unittest -q", "allowed_changes": ["ring.py"]},
    "fresh-a-stable-unique": {"verify": "python3 -m unittest -q", "allowed_changes": ["records.py"]},
    "fresh-b-balanced-brackets": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["balanced_brackets.py"]},
    "fresh-b-chunk-list": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["chunk_list.py"]},
    "fresh-b-date-range": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["date_range.py"]},
    "fresh-b-dedupe-records": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["dedupe_records.py"]},
    "fresh-b-iso-week-labels": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["iso_week_labels.py"]},
    "fresh-b-merge-counts": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["merge_counts.py"]},
    "fresh-b-normalize-tags": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["normalize_tags.py"]},
    "fresh-b-rotate-list": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["rotate_list.py"]},
    "fresh-b-running-peaks": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["running_peaks.py"]},
    "fresh-b-validate-port": {"verify": "python3 -m unittest discover -s tests -q", "allowed_changes": ["validate_port.py"]},
}
CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
XML_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([A-Za-z_][A-Za-z0-9_]*)>\s*(.*?)\s*</function>\s*</tool_call>",
    re.DOTALL,
)
XML_PARAMETER_RE = re.compile(
    r"<parameter=([A-Za-z_][A-Za-z0-9_]*)>(.*?)</parameter>",
    re.DOTALL,
)


def contained(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or raw.startswith("/"):
        raise ValueError("path_outside_task")
    path = (root / raw).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path_outside_task")
    if "__pycache__" in path.parts:
        raise ValueError("bytecode_paths_are_forbidden")
    return path


def execute_bash(root: Path, arguments: dict) -> str:
    command = arguments.get("command")
    if not isinstance(command, str) or not command.strip():
        return "ERROR command must be a nonempty string"
    lowered = command.lower()
    blocked = (
        "curl ", "wget ", "git push", "git checkout", "git reset", "git restore",
        "git switch", "git stash", "git clean", "sudo ", "ssh ", "scp ", "rsync ",
        "rm ", "rm\t", "unlink ", "rmdir ", "shred ", "../", "/etc/", "/.ssh",
        "pip install", "python -m pip", "git commit", "git add", "find -delete",
        "find . -delete", "python3 -c", "python -c", "bash -c", "sh -c",
        "py_compile", "compileall", "cd ", "pushd ", "popd ", "eval ", "exec ",
        "/proc/", "/sys/", "/dev/fd", "$", "`", ";", "&&", "||", "\n", "\r",
    )
    if any(item in lowered for item in blocked):
        return "ERROR command rejected by evaluation policy"
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "ERROR command rejected by evaluation policy"
    forbidden_executables = {
        "curl", "wget", "ssh", "scp", "rsync", "nc", "ncat", "socat", "sudo",
        "rm", "unlink", "rmdir", "shred", "mv", "ln", "env", "printenv", "docker",
        "podman", "chmod", "chown", "kill", "pkill", "mount", "umount",
    }
    if any(Path(token).name in forbidden_executables for token in tokens):
        return "ERROR command rejected by evaluation policy"
    if any(token.startswith("/") or ".." in Path(token).parts for token in tokens if token not in {"/dev/null"}):
        return "ERROR command rejected by evaluation policy"
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            command,
            cwd=root,
            shell=True,
            executable="/bin/bash",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "ERROR command timed out"
    output = result.stdout[-6000:]
    return f"exit={result.returncode}\n{output}"


def str_replace_editor(root: Path, arguments: dict) -> str:
    try:
        path = contained(root, arguments.get("path", ""))
    except (TypeError, ValueError):
        return "ERROR invalid path"
    command = arguments.get("command")
    try:
        if command == "view":
            if path.is_dir():
                return "\n".join(sorted(item.name for item in path.iterdir()))[:6000]
            text = path.read_text()
            view_range = arguments.get("view_range")
            if isinstance(view_range, list) and len(view_range) == 2:
                lines = text.splitlines()
                start = max(1, int(view_range[0]))
                end = min(len(lines), int(view_range[1]))
                text = "\n".join(lines[start - 1 : end])
            return text[:6000]
        if command == "create":
            if path.exists():
                return "ERROR file already exists"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(arguments.get("file_text", "")))
            return "OK file created"
        if command == "str_replace":
            old = arguments.get("old_str")
            new = arguments.get("new_str")
            if not isinstance(old, str) or not isinstance(new, str) or not old:
                return "ERROR old_str/new_str invalid"
            text = path.read_text()
            if text.count(old) != 1:
                return f"ERROR old_str occurrence count={text.count(old)}"
            path.write_text(text.replace(old, new, 1))
            return "OK replacement applied"
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return f"ERROR {type(exc).__name__}"
    return "ERROR unsupported editor command"


def parse_call(text: str) -> tuple[dict | None, str]:
    match = CALL_RE.search(text)
    if match:
        try:
            call = json.loads(match.group(1))
            name = call.get("name")
            arguments = call.get("arguments")
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if name not in {"execute_bash", "str_replace_editor"} or not isinstance(arguments, dict):
                return None, text
            public = (text[: match.start()] + text[match.end() :]).replace("<|im_end|>", "").strip()
            return {"name": name, "arguments": arguments}, public
        except (json.JSONDecodeError, AttributeError):
            return None, text

    match = XML_CALL_RE.search(text)
    if not match:
        return None, text
    name = match.group(1)
    if name not in {"execute_bash", "str_replace_editor"}:
        return None, text
    arguments: dict[str, object] = {}
    for parameter in XML_PARAMETER_RE.finditer(match.group(2)):
        key = parameter.group(1)
        if key in arguments:
            return None, text
        raw_value = parameter.group(2)
        if raw_value.startswith("\r\n"):
            raw_value = raw_value[2:]
        elif raw_value.startswith("\n"):
            raw_value = raw_value[1:]
        if raw_value.endswith("\r\n"):
            raw_value = raw_value[:-2]
        elif raw_value.endswith("\n"):
            raw_value = raw_value[:-1]
        value: object = raw_value
        if key == "view_range":
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return None, text
        arguments[key] = value
    if not arguments:
        return None, text
    public = (text[: match.start()] + text[match.end() :]).replace("<|im_end|>", "").strip()
    return {"name": name, "arguments": arguments}, public


def ignored_snapshot_path(root: Path, path: Path) -> bool:
    return bool(IGNORED_SNAPSHOT_PARTS.intersection(path.relative_to(root).parts))


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not ignored_snapshot_path(root, path)
    }


def text_snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not ignored_snapshot_path(root, path):
            try:
                result[str(path.relative_to(root))] = path.read_text()
            except UnicodeError:
                continue
    return result


def unified_changes(before: dict[str, str], after: dict[str, str]) -> str:
    chunks: list[str] = []
    for name in sorted(set(before) | set(after)):
        if before.get(name) == after.get(name):
            continue
        chunks.extend(difflib.unified_diff(
            before.get(name, "").splitlines(keepends=True),
            after.get(name, "").splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
        ))
    return "".join(chunks)


def tree_sha256(root: Path) -> str:
    return hashlib.sha256(
        json.dumps(tree_hashes(root), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adapter_metadata(adapter: str | None) -> dict:
    if adapter is None:
        return {"path": None, "config_sha256": None, "weights_sha256": None}
    root = Path(adapter)
    config = root / "adapter_config.json"
    weights = root / "adapter_model.safetensors"
    result = {
        "path": str(root),
        "config_sha256": file_sha256(config),
        "weights_sha256": file_sha256(weights),
    }
    export_manifest = root / "export_manifest.json"
    if export_manifest.exists():
        result["export_manifest_sha256"] = file_sha256(export_manifest)
        result["export_manifest"] = json.loads(export_manifest.read_text())
    return result


def verify_loaded_adapter(model, adapter: str) -> dict:
    root = Path(adapter)
    config = json.loads((root / "adapter_config.json").read_text())
    if config.get("base_model_name_or_path") != MODEL:
        raise RuntimeError("adapter base model does not match pinned model")
    manifest = json.loads((root / "export_manifest.json").read_text())
    if manifest.get("model") != MODEL or manifest.get("revision") != MODEL_REVISION:
        raise RuntimeError("adapter export model or revision does not match the pin")
    if manifest["source"]["adapter_weights_sha256"] != SOURCE_ADAPTER_WEIGHTS_SHA256:
        raise RuntimeError("adapter export does not derive from the verified final checkpoint")
    if manifest["output"]["adapter_config_sha256"] != file_sha256(root / "adapter_config.json"):
        raise RuntimeError("adapter export config hash does not match its manifest")
    if manifest["output"]["adapter_weights_sha256"] != file_sha256(root / "adapter_model.safetensors"):
        raise RuntimeError("adapter export weight hash does not match its manifest")
    with safe_open(root / "adapter_model.safetensors", framework="pt", device="cpu") as handle:
        expected = {name: handle.get_tensor(name) for name in handle.keys()}
    loaded = {
        name: tensor
        for name, tensor in get_peft_model_state_dict(model).items()
        if ".lora_" in name
    }
    if set(loaded) != set(expected):
        missing = sorted(set(expected) - set(loaded))
        unexpected = sorted(set(loaded) - set(expected))
        raise RuntimeError(f"adapter state mismatch missing={missing[:3]} unexpected={unexpected[:3]}")
    mismatched = [
        name for name, tensor in loaded.items()
        if not torch.equal(tensor.detach().cpu(), expected[name])
    ]
    if mismatched:
        raise RuntimeError(f"adapter tensor mismatch: {mismatched[:3]}")
    return {
        "loaded_state_verified": True,
        "loaded_tensor_count": len(loaded),
        "loaded_parameter_count": sum(tensor.numel() for tensor in loaded.values()),
    }


def run_task(
    model,
    tokenizer,
    arm: str,
    adapter: dict,
    template_root: Path,
    run_root: Path,
    task_id: str,
    harness_sha256: str,
    debug: bool,
) -> dict:
    task_root = run_root / arm / task_id
    if task_root.exists():
        shutil.rmtree(task_root)
    shutil.copytree(template_root / task_id, task_root)
    before = tree_hashes(task_root)
    before_text = text_snapshot(task_root)
    user = (task_root / "README.md").read_text()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
    trace: list[str] = []
    observability_events: list[dict] = []
    raw_response_hashes: list[str] = []
    invalid_responses = 0
    terminal_responses = 0
    execution_errors = 0
    last_text = ""
    for turn in range(MAX_TURNS):
        prompt = tokenizer.apply_chat_template(
            messages,
            tools=TOOLS,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        last_text = tokenizer.decode(output[0, inputs["input_ids"].shape[1] :], skip_special_tokens=False)
        raw_response_hashes.append(hashlib.sha256(last_text.encode()).hexdigest())
        call, public_content = parse_call(last_text)
        observability_events.append({
            "type": "generation",
            "name": f"turn-{turn}",
            "input": {
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "input_tokens": int(inputs["input_ids"].shape[1]),
            },
            "output": {
                "response_sha256": raw_response_hashes[-1],
                "output_tokens": int(output.shape[1] - inputs["input_ids"].shape[1]),
                "parsed_tool": call["name"] if call else None,
                "public_content": public_content[:2000] if public_content else "",
            },
        })
        if call is None:
            if "<tool_call>" in last_text:
                invalid_responses += 1
            else:
                terminal_responses += 1
            if debug:
                print(json.dumps({"task_id": task_id, "raw_preview": last_text[:2000]}), flush=True)
            break
        call_id = f"call_{turn}"
        messages.append({
            "role": "assistant",
            "content": public_content or None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }],
        })
        if call["name"] == "execute_bash":
            observation = execute_bash(task_root, call["arguments"])
        else:
            observation = str_replace_editor(task_root, call["arguments"])
        if observation.startswith("ERROR"):
            execution_errors += 1
        trace.append(call["name"])
        observability_events.append({
            "type": "tool",
            "name": call["name"],
            "input": call["arguments"],
            "output": observation,
            "output_sha256": hashlib.sha256(observation.encode()).hexdigest(),
            "error": observation.startswith("ERROR"),
        })
        messages.append({"role": "tool", "tool_call_id": call_id, "content": observation})

    try:
        verify = subprocess.run(
            TASKS[task_id]["verify"],
            cwd=task_root,
            shell=True,
            executable="/bin/bash",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            env={"PATH": os.environ.get("PATH", ""), "HOME": str(task_root), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        verify_exit = verify.returncode
        verify_output = verify.stdout
    except subprocess.TimeoutExpired as exc:
        verify_exit = 124
        verify_output = f"ERROR verification timed out after {exc.timeout} seconds"
    after = tree_hashes(task_root)
    after_text = text_snapshot(task_root)
    changed_files = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    allowed_changes = set(TASKS[task_id]["allowed_changes"])
    policy_violations = sorted(set(changed_files) - allowed_changes)
    tests_tampered = any(Path(path).name.startswith("test_") for path in changed_files)
    return {
        "arm": arm,
        "task_id": task_id,
        "passed": verify_exit == 0 and not policy_violations,
        "verify_exit": verify_exit,
        "verify_sha256": hashlib.sha256(verify_output.encode()).hexdigest(),
        "turns": len(trace),
        "generations": len(raw_response_hashes),
        "invalid_responses": invalid_responses,
        "terminal_responses": terminal_responses,
        "execution_errors": execution_errors,
        "tool_calls": trace,
        "changed_files": changed_files,
        "allowed_changes": sorted(allowed_changes),
        "policy_violations": policy_violations,
        "tests_tampered": tests_tampered,
        "unified_diff": unified_changes(before_text, after_text),
        "messages": messages,
        "observability_events": observability_events,
        "response_sha256": raw_response_hashes,
        "model": MODEL,
        "revision": MODEL_REVISION,
        "adapter": adapter,
        "harness_version": HARNESS_VERSION,
        "harness_sha256": harness_sha256,
        "system_prompt_sha256": SYSTEM_PROMPT_SHA256,
        "tools_sha256": TOOLS_SHA256,
        "max_turns": MAX_TURNS,
        "max_new_tokens": MAX_NEW_TOKENS,
        "task_fixture_sha256": hashlib.sha256(
            json.dumps(before, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def task_error_result(
    arm: str,
    adapter: dict,
    template_root: Path,
    task_id: str,
    harness_sha256: str,
    exc: Exception,
) -> dict:
    fixture_hashes = tree_hashes(template_root / task_id)
    error = f"{type(exc).__name__}: {exc}"
    return {
        "arm": arm,
        "task_id": task_id,
        "passed": False,
        "verify_exit": None,
        "verify_sha256": hashlib.sha256(error.encode()).hexdigest(),
        "turns": 0,
        "generations": 0,
        "invalid_responses": 0,
        "terminal_responses": 0,
        "execution_errors": 1,
        "tool_calls": [],
        "changed_files": [],
        "allowed_changes": sorted(TASKS[task_id]["allowed_changes"]),
        "policy_violations": [],
        "tests_tampered": False,
        "unified_diff": "",
        "messages": [],
        "observability_events": [{"type": "harness_error", "name": type(exc).__name__, "output": error}],
        "response_sha256": [],
        "model": MODEL,
        "revision": MODEL_REVISION,
        "adapter": adapter,
        "harness_version": HARNESS_VERSION,
        "harness_sha256": harness_sha256,
        "system_prompt_sha256": SYSTEM_PROMPT_SHA256,
        "tools_sha256": TOOLS_SHA256,
        "max_turns": MAX_TURNS,
        "max_new_tokens": MAX_NEW_TOKENS,
        "task_fixture_sha256": hashlib.sha256(
            json.dumps(fixture_hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "harness_error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    parser.add_argument("--adapter")
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--training-config", type=Path)
    parser.add_argument("--data-manifest", type=Path)
    parser.add_argument("--task", action="append", choices=sorted(TASKS))
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--templates", type=Path, default=Path("/workspace/eval/templates"))
    parser.add_argument("--runs", type=Path, default=Path("/workspace/eval/runs"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observability-dir", type=Path, default=Path("/workspace/eval/observability"))
    args = parser.parse_args()
    args.lock = args.lock.resolve()
    args.templates = args.templates.resolve()
    args.runs = args.runs.resolve()
    args.output = args.output.resolve()
    args.observability_dir = args.observability_dir.resolve()
    if os.environ.get("MINI_GIBSON_EVAL_CONTAINER") != "1":
        raise SystemExit("evaluation must run in the locked-down container")
    if args.arm == "base" and args.adapter:
        raise SystemExit("base arm cannot load an adapter")
    if args.arm != "base" and not args.adapter:
        raise SystemExit("non-base arm requires an adapter")
    lock = json.loads(args.lock.read_text())
    harness_sha256 = file_sha256(Path(__file__))
    if lock["harness_sha256"] != harness_sha256:
        raise SystemExit("harness hash does not match lock")
    observability_sha256 = file_sha256(Path(__file__).with_name("observability.py"))
    if lock["observability_sha256"] != observability_sha256:
        raise SystemExit("observability policy hash does not match lock")
    if lock["fixtures_sha256"] != tree_sha256(args.templates):
        raise SystemExit("fixture hash does not match lock")
    if lock["system_prompt_sha256"] != SYSTEM_PROMPT_SHA256 or lock["tools_sha256"] != TOOLS_SHA256:
        raise SystemExit("agent contract does not match lock")
    if lock["agent_contract_sha256"] != file_sha256(Path(__file__).with_name("agent_contract.py")):
        raise SystemExit("agent contract file does not match lock")
    if lock["entrypoint_sha256"] != file_sha256(Path(__file__).with_name("lightning_eval_v3_entry.py")):
        raise SystemExit("entrypoint does not match lock")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION)
    base = AutoModelForCausalLM.from_pretrained(
        MODEL,
        revision=MODEL_REVISION,
        dtype=torch.bfloat16,
        device_map="cuda",
    )
    model = PeftModel.from_pretrained(base, args.adapter) if args.adapter else base
    model.eval()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    selected = args.task or list(TASKS)
    adapter = adapter_metadata(args.adapter)
    if args.adapter:
        adapter.update(verify_loaded_adapter(model, args.adapter))
    chat_template = tokenizer.chat_template
    chat_template_sha256 = hashlib.sha256(
        (chat_template if isinstance(chat_template, str) else json.dumps(chat_template, sort_keys=True)).encode()
    ).hexdigest()
    provenance = {
        "lock_sha256": file_sha256(args.lock),
        "observability_sha256": observability_sha256,
        "fixtures_sha256": lock["fixtures_sha256"],
        "chat_template_sha256": chat_template_sha256,
        "training_config_sha256": file_sha256(args.training_config) if args.training_config else None,
        "data_manifest_sha256": file_sha256(args.data_manifest) if args.data_manifest else None,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "cuda_version": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
    }
    results = []
    args.output.write_text("")
    for task in selected:
        try:
            row = run_task(
                model, tokenizer, args.arm, adapter, args.templates, args.runs, task, harness_sha256, args.debug
            )
        except Exception as exc:
            row = task_error_result(args.arm, adapter, args.templates, task, harness_sha256, exc)
        row["provenance"] = provenance
        results.append(row)
        with args.output.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    observability_paths = export_observability(
        results,
        args.observability_dir,
    )
    print(json.dumps({
        "arm": args.arm,
        "observability_records": len(observability_paths),
        "passed": sum(row["passed"] for row in results),
        "tasks": len(results),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
