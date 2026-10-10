#!/usr/bin/env python3
"""trace_export.py: clean traces → chat-format training JSONL (DRAFT for issue #6).

Reads ONLY $GIBSON_TRACE_ROOT/clean/**/record.json run dirs. Emits one JSON object per run:
  {"run_id", "repo", "runner", "role", "label", "messages": [...]}
with OpenAI-style messages (role/content, assistant tool_calls, tool results), which vLLM chat templates accept.

Vendor tools are normalized to: read_file, write_file, edit_file, run_command, search, other:<name>.

Usage:
  python trace_export.py --root ~/gibson-traces --cutoff 2026-10-12 --out data/ [--only-verified] [--premature] [--freeze]

Splits by started_at: before cutoff → train.jsonl; on/after → heldout.jsonl.
--freeze writes heldout.manifest.json; later runs refuse to place any frozen run in train.
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

TOOL_MAP_VERSION = "2"
TOOL_MAP = {
    # Claude Code
    "Read": "read_file", "Write": "write_file", "Edit": "edit_file", "MultiEdit": "edit_file",
    "NotebookEdit": "edit_file", "Bash": "run_command", "Grep": "search", "Glob": "search",
    # Codex (item types)
    "command_execution": "run_command", "file_change": "edit_file",
    # Grok CLI 1.0.x (names seen in ~/.grok/sessions, 2026-10-04)
    "run_terminal_command": "run_command", "read_file": "read_file", "search_replace": "edit_file",
    "write": "write_file", "grep": "search", "list_dir": "search",
}


def norm_tool(name: str) -> str:
    return TOOL_MAP.get(name, f"other:{name}")


def _jsonl(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return "" if content is None else str(content)


def _tool_result_text(content) -> str:
    """Grok's Messages-format stream wraps tool output in a JSON envelope with the output as a byte
    array; `output_for_prompt` is the text the model actually saw. Claude results pass through."""
    text = _text_of(content)
    if text.startswith("{") and '"output_for_prompt"' in text:
        try:
            return str(json.loads(text).get("output_for_prompt", text))
        except ValueError:
            pass
    return text


def claude_messages(path: Path) -> list[dict]:
    """Claude stream-json (and session transcripts, which share the message shape)."""
    msgs: list[dict] = []
    for ev in _jsonl(path):
        t = ev.get("type")
        msg = ev.get("message") or {}
        content = msg.get("content")
        if t == "assistant" and isinstance(content, list):
            text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text").strip()
            calls = [
                {"id": c.get("id", ""), "type": "function",
                 "function": {"name": norm_tool(c.get("name", "")), "arguments": json.dumps(c.get("input", {}), sort_keys=True)}}
                for c in content if c.get("type") == "tool_use"
            ]
            m = {"role": "assistant", "content": text}
            if calls:
                m["tool_calls"] = calls
            if text or calls:
                msgs.append(m)
        elif t == "user":
            if isinstance(content, list):
                for c in content:
                    if c.get("type") == "tool_result":
                        msgs.append({"role": "tool", "tool_call_id": c.get("tool_use_id", ""),
                                     "content": _tool_result_text(c.get("content"))})
                    elif c.get("type") == "text" and c.get("text", "").strip():
                        msgs.append({"role": "user", "content": c["text"]})
            elif isinstance(content, str) and content.strip():
                msgs.append({"role": "user", "content": content})
        elif t == "result" and ev.get("result") and not (msgs and msgs[-1]["role"] == "assistant"
                                                        and msgs[-1]["content"] == ev["result"]):
            msgs.append({"role": "assistant", "content": ev["result"]})
    return msgs


def codex_messages(path: Path) -> list[dict]:
    """Codex `exec --json`. Event names vary by version; unknown events are skipped. VERIFY against a real fixture."""
    msgs: list[dict] = []
    n = 0
    for ev in _jsonl(path):
        item = ev.get("item") if ev.get("type") == "item.completed" else None
        if not item:
            continue
        it = item.get("type")
        if it == "agent_message":
            msgs.append({"role": "assistant", "content": item.get("text", "")})
        elif it in ("command_execution", "file_change"):
            n += 1
            cid = item.get("id") or f"codex_{n}"
            args = {"command": item.get("command")} if it == "command_execution" else {"changes": item.get("changes")}
            msgs.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": norm_tool(it), "arguments": json.dumps(args, sort_keys=True)}}]})
            out = item.get("aggregated_output") if it == "command_execution" else json.dumps(item.get("changes"))
            if item.get("exit_code") is not None:
                out = f"{out}\n[exit_code={item['exit_code']}]"
            msgs.append({"role": "tool", "tool_call_id": cid, "content": out or ""})
    return msgs


def run_messages(run: Path) -> tuple[list[dict], str]:
    prompt = run / "prompt.md"
    head = [{"role": "user", "content": prompt.read_text(encoding="utf-8", errors="replace")}] if prompt.exists() else []
    for name, fn in (("events.claude.jsonl", claude_messages), ("events.claude-session.jsonl", claude_messages),
                     ("events.grok.jsonl", claude_messages), ("events.codex.jsonl", codex_messages)):
        f = run / name
        if f.exists():
            body = fn(f)
            # Session transcripts already contain the opening user turn.
            return (body if name.endswith("session.jsonl") else head + body), name
    return [], "unsupported"


def label_of(rec: dict) -> str:
    h = (rec.get("labels") or {}).get("harness") or {}
    ti = h.get("test_integrity") or {}
    if ti and ti.get("ok") is False:
        return "test_tampering"
    if h.get("premature_completion") is True:
        return "premature_completion"
    if h.get("gate_exit") == 0:
        return "verified"
    if h.get("gate_exit") not in (None, 0):
        return "failed_honest"
    return "unlabeled"


def file_sha(run: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(run.iterdir()):
        if f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def collect(root: Path) -> list[tuple[Path, dict]]:
    clean = root / "clean"
    if not clean.is_dir():
        raise SystemExit(f"no clean/ under {root} (export reads scrubbed traces only)")
    out = []
    for rec_path in sorted(clean.rglob("record.json")):
        try:
            out.append((rec_path.parent, json.loads(rec_path.read_text())))
        except json.JSONDecodeError:
            continue
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path.home() / "gibson-traces"))
    ap.add_argument("--cutoff", required=True, help="YYYY-MM-DD; runs on/after go to held-out")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only-verified", action="store_true")
    ap.add_argument("--premature", action="store_true", help="also emit premature-completion runs as negatives")
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args(argv)

    root, out = Path(a.root).expanduser(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "heldout.manifest.json"
    frozen = set(json.loads(manifest_path.read_text())["run_ids"]) if manifest_path.exists() else set()

    train, held, summary = [], [], Counter()
    for run, rec in collect(root):
        label = label_of(rec)
        keep = label == "verified" or (a.premature and label in ("premature_completion", "test_tampering"))
        if a.only_verified and not keep:
            summary["skipped_filter"] += 1
            continue
        msgs, src = run_messages(run)
        if not msgs:
            summary["skipped_unsupported"] += 1
            continue
        row = {"run_id": rec.get("run_id"), "repo": rec.get("repo"), "runner": rec.get("runner"),
               "role": rec.get("role"), "label": label, "source": src, "tool_map_version": TOOL_MAP_VERSION,
               "sha256": file_sha(run), "messages": msgs}
        started = (rec.get("started_at") or rec.get("ended_at") or "")[:10]
        is_held = rec.get("run_id") in frozen or (started and started >= a.cutoff)
        (held if is_held else train).append(row)
        summary[f"label:{label}"] += 1
        summary[f"runner:{rec.get('runner')}"] += 1
        summary[f"repo:{rec.get('repo')}"] += 1

    leaked = {r["run_id"] for r in train} & frozen
    if leaked:
        raise SystemExit(f"refusing: frozen held-out runs would enter train: {sorted(leaked)}")

    for name, rows in (("train.jsonl", train), ("heldout.jsonl", held)):
        with open(out / name, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    if a.freeze:
        manifest_path.write_text(json.dumps({"cutoff": a.cutoff, "run_ids": sorted(r["run_id"] for r in held),
                                             "sha256": {r["run_id"]: r["sha256"] for r in held}}, indent=2))
    total = summary.get("label:premature_completion", 0) + summary.get("label:verified", 0) + summary.get("label:failed_honest", 0)
    report = {"train": len(train), "heldout": len(held), "counts": dict(sorted(summary.items())),
              "premature_completion_rate": round(summary.get("label:premature_completion", 0) / total, 3) if total else None}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
