"""Build historical SFT records from merged on-host agent sessions.

Reads the inventory CSV and PR metadata. Writes JSONL outside the repo.
Session paths are hashed into provenance and are not stored.

Usage: python3 training/historical/extract.py --csv PATH --prs-dir PATH --out PATH --stats PATH [--train PATH --holdout PATH]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from training.historical.redact import drop_if_residual, redact_record, redact_text, residual_names  # noqa: E402
from training.historical.validate import (
    EPISODE_TOKEN_LIMIT,
    TOOL_TOKEN_LIMIT,
    check_record,
    estimate_tokens,
    load_schema,
    messages_tokens,
    render_stats,
    validate_jsonl,
)

ORG = "The-AIE"
SAMPLE_SEED = 414
TRAIN_TOKEN_CAP = 16_000_000
HOLDOUT_FRACTION = 0.15
ISSUE_BODY_CHARS = 1500
SYSTEM_PROMPT = (
    "You are an engineering agent completing a software task that landed as a merged pull request. "
    "Use tools to inspect and change the repo. Treat tool results as the only evidence."
)

# Vendor names normalized to one tool set. Unknown names pass through as other:<name>.
TOOL_MAP = {
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "edit_file",
    "MultiEdit": "edit_file",
    "NotebookEdit": "edit_file",
    "Bash": "run_command",
    "Grep": "search",
    "Glob": "search",
    "command_execution": "run_command",
    "file_change": "edit_file",
    "run_terminal_command": "run_command",
    "read_file": "read_file",
    "search_replace": "edit_file",
    "write": "write_file",
    "grep": "search",
    "list_dir": "search",
    "exec": "run_command",
    "shell": "run_command",
    "local_shell": "run_command",
    "apply_patch": "edit_file",
}

PR_FILES = {
    "conference-os": "prs.conference-os.json",
    "chatterbuilt": "prs.chatterbuilt.json",
    "the-gibson": "prs.the-gibson.json",
}

_CALL_TYPES = {"function_call", "custom_tool_call", "local_shell_call", "tool_call"}
_OUTPUT_TYPES = {
    "function_call_output",
    "custom_tool_call_output",
    "local_shell_call_output",
    "tool_call_output",
}
_ROLLOUT_TYPES = {"response_item", "session_meta", "event_msg", "turn_context", "world_state", "compacted"}


class ParseSkip(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class IdMap:
    """Keep tool-call ids unique without losing the call/result pairing."""

    def __init__(self) -> None:
        self._used: set[str] = set()
        self._last: dict[str, str] = {}

    def call(self, raw: str) -> str:
        base = raw or "call"
        nid = base
        n = 2
        while nid in self._used:
            nid = f"{base}_{n}"
            n += 1
        self._used.add(nid)
        self._last[base] = nid
        return nid

    def result(self, raw: str) -> str:
        base = raw or "call"
        return self._last.get(base, base)


def norm_tool(name: str) -> str:
    if not name:
        return "other:tool"
    return TOOL_MAP.get(name, f"other:{name}")


def parts_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits = []
        for item in content:
            if isinstance(item, str):
                bits.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    bits.append(str(item.get("text") or ""))
                elif "content" in item:
                    bits.append(parts_text(item.get("content")))
            else:
                bits.append(str(item))
        return "\n".join(bits)
    if isinstance(content, dict):
        if "text" in content:
            return str(content.get("text") or "")
        if "content" in content:
            return parts_text(content.get("content"))
        return ""
    return str(content)


def unwrap_tool_text(content) -> str:
    """Grok stream envelopes store the text the model saw in output_for_prompt."""
    text = parts_text(content)
    stripped = text.lstrip()
    if stripped.startswith("{") and "output_for_prompt" in stripped[:8000]:
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            return text
        if isinstance(obj, dict) and "output_for_prompt" in obj:
            return str(obj.get("output_for_prompt") or "")
    return text


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def sniff(path: Path) -> str:
    types: set[str] = set()
    seen = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                seen += 1
                if seen > 40:
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get("type"), str):
                    types.add(obj["type"])
    except OSError as exc:
        raise ParseSkip("unreadable") from exc
    if types & _ROLLOUT_TYPES:
        return "codex_rollout"
    if "item.completed" in types or "thread.started" in types:
        return "codex_exec"
    if "assistant" in types or "user" in types:
        return "claude_stream"
    return "unknown"


def _arguments_for_call(payload: dict) -> str:
    raw_args = payload.get("arguments")
    if isinstance(raw_args, str) and raw_args.strip():
        return raw_args
    if isinstance(raw_args, dict):
        return json.dumps(raw_args, sort_keys=True, default=str)
    raw = payload.get("input")
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            json.loads(raw)
            return raw
        except json.JSONDecodeError:
            pass
    if isinstance(raw, str):
        return json.dumps({"command": raw}, sort_keys=True)
    action = payload.get("action")
    if isinstance(action, dict):
        cmd = action.get("command")
        if isinstance(cmd, list):
            return json.dumps({"command": " ".join(str(part) for part in cmd)}, sort_keys=True)
        if isinstance(cmd, str):
            return json.dumps({"command": cmd}, sort_keys=True)
    return "{}"


def _call_name(payload: dict) -> str:
    name = payload.get("name") or ""
    if not name and isinstance(payload.get("action"), dict):
        name = payload["action"].get("type") or "exec"
    if not name:
        name = "exec" if payload.get("type") == "custom_tool_call" else (payload.get("type") or "tool")
    return str(name)


def _output_text(payload: dict) -> str:
    out = payload.get("output")
    if out is None:
        out = payload.get("aggregated_output")
    text = unwrap_tool_text(out)
    if payload.get("exit_code") is not None:
        text = f"{text}\n[exit_code={payload['exit_code']}]"
    return text


def parse_codex_rollout(path: Path) -> list[dict]:
    """Codex session JSONL (~/.codex/sessions rollout-*.jsonl)."""
    ids = IdMap()
    messages: list[dict] = []
    pending: list[dict] = []

    def flush() -> None:
        nonlocal pending
        if pending:
            messages.append({"role": "assistant", "content": "", "tool_calls": pending})
            pending = []

    for obj in iter_jsonl(path):
        if obj.get("type") != "response_item":
            continue
        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        ptype = payload.get("type")
        if ptype == "message":
            role = payload.get("role")
            if role in ("developer", "system"):
                continue
            text = parts_text(payload.get("content")).strip()
            if not text:
                continue
            flush()
            if role == "user":
                messages.append({"role": "user", "content": text})
            elif role == "assistant":
                messages.append({"role": "assistant", "content": text})
        elif ptype in _CALL_TYPES:
            pending.append({
                "id": ids.call(str(payload.get("call_id") or payload.get("id") or "")),
                "type": "function",
                "function": {"name": norm_tool(_call_name(payload)), "arguments": _arguments_for_call(payload)},
            })
        elif ptype in _OUTPUT_TYPES:
            flush()
            messages.append({
                "role": "tool",
                "tool_call_id": ids.result(str(payload.get("call_id") or payload.get("id") or "")),
                "content": _output_text(payload),
            })
    flush()
    return messages


def parse_codex_exec(path: Path) -> list[dict]:
    """Codex `exec --json` item stream. Same shape as tests/evaluation/fixtures/codex*.jsonl."""
    ids = IdMap()
    messages: list[dict] = []
    for obj in iter_jsonl(path):
        item = obj.get("item") if obj.get("type") == "item.completed" else None
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "agent_message":
            text = str(item.get("text") or "")
            if text.strip():
                messages.append({"role": "assistant", "content": text})
        elif kind in ("command_execution", "file_change"):
            cid = ids.call(str(item.get("id") or ""))
            if kind == "command_execution":
                args = json.dumps({"command": item.get("command")}, sort_keys=True)
                out = unwrap_tool_text(item.get("aggregated_output") or "")
                if item.get("exit_code") is not None:
                    out = f"{out}\n[exit_code={item['exit_code']}]"
            else:
                args = json.dumps({"changes": item.get("changes")}, sort_keys=True, default=str)
                out = json.dumps(item.get("changes"), default=str)
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": cid,
                    "type": "function",
                    "function": {"name": norm_tool(kind), "arguments": args},
                }],
            })
            messages.append({"role": "tool", "tool_call_id": cid, "content": out})
    return messages


def parse_claude_stream(path: Path) -> list[dict]:
    """Claude session JSONL and the Grok fixture stream, which shares this shape."""
    ids = IdMap()
    messages: list[dict] = []
    for obj in iter_jsonl(path):
        kind = obj.get("type")
        msg = obj.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        if kind == "assistant" and isinstance(content, list):
            texts = []
            calls = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and str(block.get("text") or "").strip():
                    texts.append(str(block.get("text") or ""))
                elif block.get("type") == "tool_use":
                    raw_in = block.get("input", {})
                    if isinstance(raw_in, str):
                        args = raw_in
                    else:
                        args = json.dumps(raw_in if isinstance(raw_in, dict) else {}, sort_keys=True, default=str)
                    calls.append({
                        "id": ids.call(str(block.get("id") or "")),
                        "type": "function",
                        "function": {"name": norm_tool(str(block.get("name") or "")), "arguments": args},
                    })
            if texts or calls:
                message = {"role": "assistant", "content": "\n".join(texts).strip()}
                if calls:
                    message["tool_calls"] = calls
                messages.append(message)
        elif kind == "user":
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        messages.append({
                            "role": "tool",
                            "tool_call_id": ids.result(str(block.get("tool_use_id") or "")),
                            "content": unwrap_tool_text(block.get("content")),
                        })
                    elif block.get("type") == "text" and str(block.get("text") or "").strip():
                        messages.append({"role": "user", "content": str(block.get("text") or "")})
            elif isinstance(content, str) and content.strip():
                messages.append({"role": "user", "content": content})
        elif kind == "result" and isinstance(obj.get("result"), str):
            text = obj["result"].strip()
            if text and not (messages and messages[-1].get("role") == "assistant" and messages[-1].get("content") == text):
                messages.append({"role": "assistant", "content": text})
    return messages


def parse_grok_chat(path: Path) -> list[dict]:
    """Grok session chat_history.jsonl (role records, not the stream fixture)."""
    ids = IdMap()
    messages: list[dict] = []
    for obj in iter_jsonl(path):
        kind = obj.get("type")
        if kind in ("system", "reasoning"):
            continue
        if kind == "user":
            if obj.get("synthetic_reason"):
                continue
            text = parts_text(obj.get("content")).strip()
            if text:
                messages.append({"role": "user", "content": text})
        elif kind == "assistant":
            calls = []
            for call in obj.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                raw_args = call.get("arguments")
                if isinstance(raw_args, str):
                    args = raw_args
                else:
                    args = json.dumps(raw_args if raw_args is not None else {}, sort_keys=True, default=str)
                calls.append({
                    "id": ids.call(str(call.get("id") or "")),
                    "type": "function",
                    "function": {"name": norm_tool(str(call.get("name") or "")), "arguments": args},
                })
            text = parts_text(obj.get("content")).strip()
            if not text and not calls:
                continue
            message: dict = {"role": "assistant", "content": text}
            if calls:
                message["tool_calls"] = calls
            messages.append(message)
        elif kind == "tool_result":
            messages.append({
                "role": "tool",
                "tool_call_id": ids.result(str(obj.get("tool_call_id") or "")),
                "content": unwrap_tool_text(obj.get("content")),
            })
    return messages


def parse_grok_dir(path: Path) -> list[dict]:
    chat = path / "chat_history.jsonl"
    if not chat.is_file():
        raise ParseSkip("no_chat_history")
    return parse_grok_chat(chat)


def parse_session(path: Path, vendor: str) -> list[dict]:
    if path.is_dir():
        return parse_grok_dir(path)
    if not path.is_file():
        raise ParseSkip("missing_file")
    kind = sniff(path)
    if kind == "unknown":
        kind = "codex_rollout" if vendor == "codex" else "claude_stream"
    if kind == "codex_rollout":
        return parse_codex_rollout(path)
    if kind == "codex_exec":
        return parse_codex_exec(path)
    return parse_claude_stream(path)


def load_prs(directory: Path) -> dict[tuple[str, int], dict]:
    index: dict[tuple[str, int], dict] = {}
    for repo, name in PR_FILES.items():
        path = directory / name
        for item in json.loads(path.read_text(encoding="utf-8")):
            number = item.get("number")
            if isinstance(number, int):
                index[(repo, number)] = item
    return index


def select_rows(csv_path: Path, host: str, states: tuple[str, ...] = ("MERGED",),
                all_hosts: bool = False) -> list[dict]:
    rows = []
    allowed = set(states)
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            if not all_hosts and row.get("host") != host:
                continue
            if row.get("pr_state") not in allowed:
                continue
            if not (row.get("pr") or "").strip():
                continue
            rows.append(row)
    return rows


def tally_join(csv_path: Path) -> dict:
    """Session counts from the inventory. Unjoined reasons live in the join column."""
    methods: dict[str, int] = {}
    reasons: dict[str, int] = {}
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            method = (row.get("join_method") or "").strip()
            if method:
                methods[method] = methods.get(method, 0) + 1
            else:
                reason = (row.get("join") or "").strip() or "no_match"
                reasons[reason] = reasons.get(reason, 0) + 1
    return {"methods": methods, "reasons": reasons}


def issue_number(row: dict, pr: dict | None) -> int | None:
    for ref in (pr or {}).get("closingIssuesReferences") or []:
        if not isinstance(ref, dict):
            continue
        repo_name = ((ref.get("repository") or {}).get("name"))
        number = ref.get("number")
        if isinstance(number, int) and (not repo_name or repo_name == row.get("repo")):
            return number
    raw = (row.get("issue") or "").strip()
    if raw.isdigit():
        return int(raw)
    return None


def build_task(row: dict, pr: dict | None) -> str:
    """User task from PR metadata. Title and issue body are used only when present."""
    title = ""
    if pr and isinstance(pr.get("title"), str):
        title = pr["title"].strip()
    branch = ""
    if pr and isinstance(pr.get("headRefName"), str):
        branch = pr["headRefName"].strip()
    if not branch:
        branch = (row.get("branch") or "").strip()
    if title:
        head = title
    else:
        head = f"PR {row.get('repo')}#{row.get('pr')}"
        if branch:
            head += f" on branch {branch}"
    lines = [head]
    linked = []
    for ref in (pr or {}).get("closingIssuesReferences") or []:
        if not isinstance(ref, dict):
            continue
        number = ref.get("number")
        body = ref.get("body") if isinstance(ref.get("body"), str) else ""
        url = ref.get("url") if isinstance(ref.get("url"), str) else ""
        if body.strip():
            linked.append(f"Linked issue #{number}:\n{body.strip()}")
        elif number is not None:
            bit = f"Linked issue #{number}"
            if url:
                bit += f" ({url})"
            linked.append(bit)
    if linked:
        lines.append("\n".join(linked))
    return "\n\n".join(lines)


def format_issue_task(title: str, body: str) -> str:
    """Issue title plus the first 1500 characters of the body."""
    head = (title or "").strip()
    text = (body or "").strip()
    if len(text) > ISSUE_BODY_CHARS:
        text = text[:ISSUE_BODY_CHARS]
    if head and text:
        return f"{head}\n\n{text}"
    return head or text


def embedded_issue(row: dict, pr: dict | None) -> tuple[str, str] | None:
    """Title and body when the PR metadata already carries an issue body."""
    title = ""
    if pr and isinstance(pr.get("title"), str):
        title = pr["title"].strip()
    for ref in (pr or {}).get("closingIssuesReferences") or []:
        if not isinstance(ref, dict):
            continue
        body = ref.get("body") if isinstance(ref.get("body"), str) else ""
        if not body.strip():
            continue
        ref_title = ref.get("title") if isinstance(ref.get("title"), str) else ""
        return (ref_title.strip() or title), body
    return None


class IssueStore:
    """Cache gh issue view responses under the trace cache, never in the repo."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._mem: dict[tuple[str, int], dict | None] = {}

    def get(self, repo: str, number: int) -> dict | None:
        key = (repo, number)
        if key in self._mem:
            return self._mem[key]
        path = self.cache_dir / f"{repo}-{number}.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
            if isinstance(data, dict) and ((data.get("title") or "").strip() or (data.get("body") or "").strip()):
                self._mem[key] = data
                return data
        data = self._fetch(repo, number)
        self._mem[key] = data
        return data

    def _fetch(self, repo: str, number: int) -> dict | None:
        # GH_FORCE_TTY colorizes --json, which is not valid JSON.
        env = os.environ.copy()
        env["GH_FORCE_TTY"] = "0"
        env["NO_COLOR"] = "1"
        env.pop("CLICOLOR_FORCE", None)
        try:
            proc = subprocess.run(
                ["gh", "issue", "view", str(number), "--repo", f"{ORG}/{repo}", "--json", "title,body"],
                capture_output=True,
                text=True,
                timeout=45,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        raw = _ANSI.sub("", proc.stdout or "")
        if proc.returncode != 0 or not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        payload = {"title": data.get("title") or "", "body": data.get("body") or ""}
        if not (payload["title"].strip() or payload["body"].strip()):
            return None
        if not output_allowed(self.cache_dir):
            return payload
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.cache_dir / f"{repo}-{number}.json", flags, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return payload


def resolve_user_task(row: dict, pr: dict | None, store: IssueStore | None) -> tuple[str, str]:
    """Return the user task and a source tag: embedded, fetched, or fallback."""
    embedded = embedded_issue(row, pr)
    if embedded is not None:
        title, body = embedded
        text = format_issue_task(title, body)
        if text:
            return text, "embedded"
    number = issue_number(row, pr)
    repo = row.get("repo") or ""
    if store is None or number is None or not repo:
        return build_task(row, pr), "fallback"
    data = store.get(repo, number)
    if not data:
        return build_task(row, pr), "fallback"
    text = format_issue_task(data.get("title") or "", data.get("body") or "")
    if not text:
        return build_task(row, pr), "fallback"
    return text, "fetched"


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PATCH_FILE = re.compile(r"\*\*\* (?:Update|Add|Delete) File|\*\*\* Move (?:File|to)")
_CMD_STRING = re.compile(r"""\bcmd\s*:\s*(?:"((?:\\.|[^"\\])*)"|'([^']*)')""")
_GIT_COMMIT = re.compile(r"(?:^|[;&|`\n]|&&|\|\|)\s*git\s+commit\b")
_REVIEW_TIE = re.compile(
    r"(?:^|\n)\s*LENS\s*:|you are an independent, adversarial code reviewer"
    r"|you are reviewing a spec|perform a bounded read-only|read-only release-readiness",
    re.IGNORECASE,
)
_VERDICT = re.compile(
    r"(?im)^[ \t]*(?:#{1,3}[ \t]*)?VERDICT[ \t]*:[ \t]*([A-Z][A-Z0-9_ -]{1,40})"
)
_GH_REVIEW = re.compile(r"(?i)\bgh\s+pr\s+review\b[^\n]*?(--approve|--request-changes|--comment)\b")


def extract_shell_commands(arguments: str) -> list[str]:
    commands: list[str] = []
    try:
        obj = json.loads(arguments)
    except json.JSONDecodeError:
        obj = None
    if isinstance(obj, dict):
        for key in ("command", "cmd"):
            value = obj.get(key)
            if isinstance(value, str):
                commands.append(value)
    for match in _CMD_STRING.finditer(arguments or ""):
        raw = match.group(1) if match.group(1) is not None else match.group(2)
        try:
            commands.append(bytes(raw, "utf-8").decode("unicode_escape"))
        except UnicodeDecodeError:
            commands.append(raw)
    return commands


def _strip_quoted(command: str) -> str:
    command = re.sub(r'"(?:\\.|[^"\\])*"', '""', command)
    command = re.sub(r"'(?:\\.|[^'\\])*'", "''", command)
    return command


def invokes_git_commit(arguments: str) -> bool:
    """True when a tool call runs git commit, not when it mentions the words."""
    commands = extract_shell_commands(arguments)
    blob = "\n".join(commands) if commands else (arguments or "")
    return _GIT_COMMIT.search(_strip_quoted(blob)) is not None


def call_writes_repo(name: str, arguments: str) -> bool:
    """True when this tool call edits the repo. Reads and searches do not."""
    if name in {"edit_file", "write_file"}:
        return True
    text = arguments or ""
    if "*** Begin Patch" in text and _PATCH_FILE.search(text):
        return True
    if "tools.apply_patch" in text:
        return True
    return False


def _review_query_text(messages: list[dict]) -> str:
    """The session's own query. Rules pasted around a <user_query> do not count."""
    chunks: list[str] = []
    plain: list[str] = []
    for message in messages:
        if message.get("role") != "user":
            continue
        text = message.get("content") or ""
        blocks = re.findall(r"<user_query>(.*?)</user_query>", text, flags=re.IGNORECASE | re.DOTALL)
        if blocks:
            chunks.extend(block for block in blocks if block.strip())
        elif text.strip():
            plain.append(text)
    if chunks:
        return "\n".join(chunks)
    return "\n".join(plain)


def recorded_verdict(messages: list[dict]) -> str:
    """Last review verdict the assistant recorded. User prompts do not count."""
    found = ""
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for match in _VERDICT.finditer(message.get("content") or ""):
            found = re.sub(r"\s+", " ", match.group(1)).strip(" -")
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            for command in extract_shell_commands(str(fn.get("arguments") or "")):
                flag = _GH_REVIEW.search(command)
                if flag:
                    found = flag.group(1).lstrip("-").replace("-", "_").upper()
    return found


def classify_session_role(messages: list[dict], sandbox: str | None) -> str:
    """builder, reviewer, or other. Tool calls decide. Keywords only break a tie."""
    wrote = False
    committed = False
    for message in messages:
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            args = str(fn.get("arguments") or "")
            if call_writes_repo(name, args):
                wrote = True
            if invokes_git_commit(args):
                committed = True
    if wrote or committed:
        return "builder"
    if sandbox == "read-only":
        return "reviewer"
    if _REVIEW_TIE.search(_review_query_text(messages)):
        return "reviewer"
    return "other"


def query_preview(messages: list[dict]) -> str:
    """First 120 characters of the session's own user query, for a spot check."""
    text = _review_query_text(messages)
    blocks = re.findall(r"<user_query>(.*?)</user_query>", text, flags=re.IGNORECASE | re.DOTALL)
    for block in blocks:
        flat = re.sub(r"\s+", " ", block).strip()
        if flat:
            return flat[:120]
    match = re.search(
        r"(?im)^(?:LENS\s*:|You are |Perform a bounded ).{0,160}",
        text,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip()[:120]
    flat = re.sub(r"\s+", " ", text).strip()
    if flat.startswith("<recommended_plugins>") or flat.startswith("<user_info>"):
        match = re.search(r"(?i)(?:you are |LENS\s*:|task\b).{0,160}", text)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()[:120]
    return flat[:120]


def session_sandbox(path: Path) -> str | None:
    """Most permissive sandbox recorded on the session. None when the file has none."""
    files = [path] if path.is_file() else list(path.glob("*.jsonl"))
    found: set[str] = set()
    for fp in files:
        try:
            handle = fp.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                if "sandbox_policy" not in line:
                    continue
                if "danger-full-access" in line:
                    found.add("danger-full-access")
                elif "workspace-write" in line:
                    found.add("workspace-write")
                elif "read-only" in line:
                    found.add("read-only")
    if "danger-full-access" in found:
        return "danger-full-access"
    if "workspace-write" in found:
        return "workspace-write"
    if "read-only" in found:
        return "read-only"
    return None


def pr_merged_at(pr: dict | None) -> str:
    if not pr:
        return ""
    value = pr.get("mergedAt")
    return value if isinstance(value, str) else ""


def holdout_pr_keys(episodes: list[dict], fraction: float = HOLDOUT_FRACTION) -> set[tuple[str, int]]:
    """Latest fraction of builder PRs by mergedAt. Undated PRs stay in the train pool."""
    dated: dict[tuple[str, int], str] = {}
    for episode in episodes:
        merged = episode.get("merged_at") or ""
        if not merged:
            continue
        key = (episode.get("repo") or "", int(episode.get("pr")))
        dated[key] = merged
    ordered = sorted(dated, key=lambda key: (dated[key], key[0], key[1]))
    count = len(ordered)
    if count == 0 or fraction <= 0:
        return set()
    hold_n = math.ceil(count * fraction - 1e-9)
    if hold_n <= 0:
        return set()
    return set(ordered[-hold_n:])


def sample_training_episodes(episodes: list[dict], cap: int, seed: int) -> list[dict]:
    """Keep every non-conference-os episode. Sample conference-os up to the token cap.

    conference-os episodes are shuffled inside each vendor, then taken round-robin
    so one vendor does not fill the cap.
    """
    must = [episode for episode in episodes if episode.get("repo") != "conference-os"]
    rest = [episode for episode in episodes if episode.get("repo") == "conference-os"]
    chosen = list(must)
    used = sum(int(episode.get("tokens") or 0) for episode in chosen)
    rng = random.Random(seed)
    buckets: dict[str, list[dict]] = {}
    for episode in rest:
        buckets.setdefault(episode.get("vendor") or "?", []).append(episode)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    order: list[dict] = []
    while any(buckets.values()):
        for vendor in sorted(buckets):
            bucket = buckets[vendor]
            if bucket:
                order.append(bucket.pop())
    for episode in order:
        tokens = int(episode.get("tokens") or 0)
        if chosen and used + tokens > cap:
            continue
        if used >= cap and chosen:
            break
        chosen.append(episode)
        used += tokens
        if used >= cap:
            break
    return chosen


def pr_url(repo: str, number: int) -> str:
    return f"https://github.com/{ORG}/{repo}/pull/{number}"


def session_provenance(path: str) -> str:
    digest = hashlib.sha256(path.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"session:{digest}"


def episode_base(row: dict) -> str:
    raw = f"{row.get('vendor')}|{row.get('session_id')}|{row.get('repo')}|{row.get('pr')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def trajectory_of(messages: list[dict], url: str, state: str = "merged") -> list[dict]:
    calls = []
    for message in messages:
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            calls.append({"kind": "tool_call", "name": fn.get("name") or "", "id": call.get("id") or ""})
    return [
        {"phase": "contract", "evidence": [{"kind": "task"}]},
        {"phase": "attempt", "evidence": calls or [{"kind": "no_tool_calls"}]},
        {"phase": "outcome", "evidence": [{"kind": "pr_state", "state": state, "url": url}]},
    ]


def useful(messages: list[dict]) -> bool:
    return any(message.get("role") in ("assistant", "tool") for message in messages)


def clip_text(text: str, max_tokens: int) -> tuple[str, bool]:
    if max_tokens <= 0:
        return "[truncated]", True
    if estimate_tokens(text) <= max_tokens:
        return text, False
    marker = "\n[truncated]"
    keep = max(0, max_tokens * 4 - len(marker))
    return text[:keep] + marker, True


def shrink_arguments(args: str, max_tokens: int) -> str:
    """Shorten tool arguments and keep them valid JSON."""
    if estimate_tokens(args) <= max_tokens:
        return args
    try:
        obj = json.loads(args)
    except json.JSONDecodeError:
        obj = {"command": args}
    budget_chars = max(32, max_tokens * 4)

    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value[:30]]
        if isinstance(value, str) and len(value) > budget_chars:
            return value[:budget_chars] + "\n[truncated]"
        return value

    text = json.dumps(walk(obj), sort_keys=True, default=str)
    if estimate_tokens(text) > max_tokens:
        return json.dumps({"truncated": True})
    return text


def truncate_tool_outputs(messages: list[dict], stats: dict, limit: int = TOOL_TOKEN_LIMIT) -> None:
    for message in messages:
        if message.get("role") != "tool":
            continue
        content = message.get("content") or ""
        before = estimate_tokens(content)
        stats["tool_outputs_seen"] += 1
        stats["tool_tokens_before"] += before
        if before > limit:
            message["content"], _did = clip_text(content, limit)
            stats["tool_outputs_truncated"] += 1
        else:
            stats["tool_outputs_kept"] += 1
        stats["tool_tokens_after"] += estimate_tokens(message.get("content") or "")


def fit_group(group: list[dict], budget: int) -> list[dict]:
    group = json.loads(json.dumps(group))
    if budget < 1:
        budget = 1
    if messages_tokens(group) <= budget:
        return group
    for _ in range(8):
        if messages_tokens(group) <= budget:
            return group
        changed = False
        for message in group:
            content = message.get("content") or ""
            if estimate_tokens(content) > 16 and messages_tokens(group) > budget:
                message["content"], did = clip_text(content, max(16, estimate_tokens(content) // 2))
                changed = changed or did
            for call in message.get("tool_calls") or []:
                fn = call.setdefault("function", {})
                args = fn.get("arguments") or ""
                if estimate_tokens(args) > 16 and messages_tokens(group) > budget:
                    fn["arguments"] = shrink_arguments(args, max(16, estimate_tokens(args) // 2))
                    changed = True
        if not changed:
            break
    if messages_tokens(group) > budget:
        for message in group:
            if message.get("role") == "tool":
                message["content"] = "[truncated]"
            elif estimate_tokens(message.get("content") or "") > 24:
                message["content"], _did = clip_text(message.get("content") or "", 24)
            for call in message.get("tool_calls") or []:
                fn = call.setdefault("function", {})
                fn["arguments"] = '{"truncated": true}'
    return group


def group_messages(body: list[dict]) -> tuple[list[list[dict]], int]:
    groups: list[list[dict]] = []
    orphans = 0
    index = 0
    while index < len(body):
        message = body[index]
        if message.get("role") == "assistant" and message.get("tool_calls"):
            ids = {call.get("id") for call in message["tool_calls"]}
            expected = len(message["tool_calls"])
            group = [message]
            nxt = index + 1
            while nxt < len(body) and body[nxt].get("role") == "tool":
                have = len(group) - 1
                if body[nxt].get("tool_call_id") in ids or have < expected:
                    group.append(body[nxt])
                    nxt += 1
                    continue
                break
            groups.append(group)
            index = nxt
        elif message.get("role") == "tool":
            orphans += 1
            index += 1
        else:
            groups.append([message])
            index += 1
    return groups, orphans


def split_windows(messages: list[dict], max_episode_tokens: int, stats: dict | None = None) -> list[list[dict]]:
    """Each window starts with the system and user task and stays within the token cap."""
    stats = stats if stats is not None else {}
    prefix: list[dict] = []
    body = list(messages)
    if body and body[0].get("role") == "system":
        prefix.append(body.pop(0))
    if body and body[0].get("role") == "user":
        prefix.append(body.pop(0))
    prefix = fit_group(prefix, max_episode_tokens)
    budget = max_episode_tokens - messages_tokens(prefix)
    if budget < 32:
        for message in prefix:
            if message.get("role") == "user":
                room = max(32, max_episode_tokens - messages_tokens([m for m in prefix if m.get("role") != "user"]) - 32)
                message["content"], _did = clip_text(message.get("content") or "", room)
        prefix = fit_group(prefix, max_episode_tokens)
        budget = max(32, max_episode_tokens - messages_tokens(prefix))
    groups, orphans = group_messages(body)
    stats["orphan_tools"] = stats.get("orphan_tools", 0) + orphans
    windows: list[list[dict]] = []
    current: list[dict] = []
    current_tokens = 0
    for group in groups:
        if messages_tokens(group) > budget:
            group = fit_group(group, budget)
        group_tokens = messages_tokens(group)
        if group_tokens > budget:
            stats["over_context"] = stats.get("over_context", 0) + 1
            continue
        if current and current_tokens + group_tokens > budget:
            windows.append(prefix + current)
            current = []
            current_tokens = 0
        current.extend(group)
        current_tokens += group_tokens
    if current or not windows:
        windows.append(prefix + current)
    return windows


def _first_user(messages: list[dict], fallback: str) -> str:
    for message in messages:
        if message.get("role") == "user":
            return message.get("content") or fallback
    return fallback


def _empty_stats() -> dict:
    return {
        "selected": 0,
        "missing_file": 0,
        "unreadable": 0,
        "parse_error": 0,
        "no_chat_history": 0,
        "empty": 0,
        "residual_secret": 0,
        "schema_invalid": 0,
        "over_context": 0,
        "pr_metadata_missing": 0,
        "usable_episodes": 0,
        "windows": 0,
        "episodes_within_limit": 0,
        "episodes_split": 0,
        "windows_from_within": 0,
        "windows_from_split": 0,
        "tool_outputs_seen": 0,
        "tool_outputs_truncated": 0,
        "tool_outputs_kept": 0,
        "tool_tokens_before": 0,
        "tool_tokens_after": 0,
        "orphan_tools": 0,
        "tokens": 0,
        "per_repo": {},
        "per_vendor": {},
        "per_role": {},
        "issue_fetched": 0,
        "issue_embedded": 0,
        "issue_fallback": 0,
        "target": 300,
        "seed": SAMPLE_SEED,
        "train_token_cap": TRAIN_TOKEN_CAP,
        "holdout_fraction": HOLDOUT_FRACTION,
        "holdout_cutoff": "",
        "builder_prs": 0,
        "holdout_prs": 0,
        "holdout_episodes": 0,
        "holdout_windows": 0,
        "holdout_tokens": 0,
        "pool_episodes": 0,
        "pool_windows": 0,
        "pool_tokens": 0,
        "train_episodes": 0,
        "train_windows": 0,
        "train_tokens": 0,
        "unsampled_episodes": 0,
        "unsampled_windows": 0,
        "unsampled_tokens": 0,
        "train_per_repo": {},
        "holdout_per_repo": {},
        "secret_hit_total": 0,
        "residual_patterns": {},
        "file_records": 0,
        "bad_json": 0,
        "schema_errors": {},
        "generated": "",
    }


def _bump(table: dict, key: str, episodes: int, windows: int, tokens: int = 0) -> None:
    cell = table.setdefault(key or "?", {"episodes": 0, "windows": 0, "tokens": 0})
    cell["episodes"] += episodes
    cell["windows"] += windows
    cell["tokens"] += tokens


def inside_git(path: Path) -> bool:
    resolved = path.resolve()
    for parent in [resolved, *resolved.parents]:
        if (parent / ".git").exists():
            return True
    return False


def output_allowed(path: Path) -> bool:
    """JSONL may only be written under the private trace root or the temp dir."""
    resolved = path.resolve()
    roots = [(Path.home() / "gibson-traces").resolve(), Path(tempfile.gettempdir()).resolve()]
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def open_private(path: Path):
    if not output_allowed(path):
        raise PermissionError("output path is outside the trace root and the temp dir")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        return os.fdopen(fd, "w", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise


def convert_row(row: dict, pr: dict | None, stats: dict, schema: dict, max_tool: int, max_episode: int,
               store: IssueStore | None = None, outcome: str = "merged") -> tuple[list[dict], dict | None]:
    """Return kept window records for one session, and episode metadata when kept."""
    path = Path(row.get("path") or "")
    if not path.exists():
        stats["missing_file"] += 1
        return [], None
    try:
        session_messages = parse_session(path, row.get("vendor") or "")
    except ParseSkip as exc:
        key = exc.reason if exc.reason in stats else "parse_error"
        stats[key] += 1
        return [], None
    except OSError:
        stats["unreadable"] += 1
        return [], None
    except Exception:
        stats["parse_error"] += 1
        return [], None
    if not useful(session_messages):
        stats["empty"] += 1
        return [], None
    if pr is None:
        stats["pr_metadata_missing"] += 1
    try:
        number = int(row["pr"])
    except (TypeError, ValueError):
        stats["parse_error"] += 1
        return [], None
    url = pr_url(row.get("repo") or "", number)
    task, task_source = resolve_user_task(row, pr, store)
    if task_source == "fetched":
        stats["issue_fetched"] += 1
    elif task_source == "embedded":
        stats["issue_embedded"] += 1
    else:
        stats["issue_fallback"] += 1
    role = classify_session_role(session_messages, session_sandbox(path))
    verdict = recorded_verdict(session_messages)
    preview = redact_text(query_preview(session_messages))
    if residual_names(preview):
        preview = ""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
        *session_messages,
    ]
    shell = {
        "episode_id": "pending",
        "repo": row.get("repo") or "",
        "issue": issue_number(row, pr),
        "pr": number,
        "task": task,
        "trajectory": trajectory_of(messages, url, outcome),
        "outcome": outcome,
        "provenance": [url, session_provenance(row.get("path") or "")],
        "messages": messages,
        "token_count": 0,
        "vendor": row.get("vendor") or "",
    }
    clean, hits = redact_record(shell)
    if hits:
        stats["residual_secret"] += 1
        for name in hits:
            stats["residual_patterns"][name] = stats["residual_patterns"].get(name, 0) + 1
        return [], None
    messages = clean["messages"]
    truncate_tool_outputs(messages, stats, max_tool)
    full_tokens = messages_tokens(messages)
    windows = split_windows(messages, max_episode, stats)
    prepared = []
    for window in windows:
        if not useful(window):
            continue
        if messages_tokens(window) > max_episode:
            stats["over_context"] += 1
            continue
        prepared.append(window)
    if not prepared:
        stats["empty"] += 1
        return [], None
    base = episode_base(row)
    prov = clean["provenance"]
    batch = []
    secret_drop = False
    schema_drop = False
    for index, window in enumerate(prepared):
        record = {
            "episode_id": f"{base}-w{index:02d}",
            "repo": clean.get("repo") or "",
            "issue": clean.get("issue"),
            "pr": clean.get("pr"),
            "task": _first_user(window, clean.get("task") or task),
            "trajectory": trajectory_of(window, url, outcome),
            "outcome": outcome,
            "provenance": prov,
            "messages": window,
            "token_count": messages_tokens(window),
            "vendor": clean.get("vendor") or "",
            "session_role": role,
            "window_index": index,
            "window_count": len(prepared),
        }
        final, residual = drop_if_residual(record)
        if final is None:
            secret_drop = True
            for name in residual:
                stats["residual_patterns"][name] = stats["residual_patterns"].get(name, 0) + 1
            continue
        errors = check_record(final, schema, max_episode)
        if errors:
            schema_drop = True
            continue
        batch.append(final)
    if not batch:
        if secret_drop:
            stats["residual_secret"] += 1
        elif schema_drop:
            stats["schema_invalid"] += 1
        else:
            stats["empty"] += 1
        return [], None
    count = len(batch)
    for index, record in enumerate(batch):
        record["window_index"] = index
        record["window_count"] = count
        record["episode_id"] = f"{base}-w{index:02d}"
    over = full_tokens > max_episode or count > 1
    if over:
        stats["episodes_split"] += 1
        stats["windows_from_split"] += count
    else:
        stats["episodes_within_limit"] += 1
        stats["windows_from_within"] += count
    token_sum = sum(record["token_count"] for record in batch)
    stats["usable_episodes"] += 1
    stats["windows"] += count
    stats["tokens"] += token_sum
    _bump(stats["per_repo"], row.get("repo") or "", 1, count, token_sum)
    _bump(stats["per_vendor"], row.get("vendor") or "", 1, count, token_sum)
    _bump(stats["per_role"], role, 1, count, token_sum)
    meta = {
        "key": base,
        "repo": row.get("repo") or "",
        "pr": number,
        "vendor": row.get("vendor") or "",
        "role": role,
        "merged_at": pr_merged_at(pr),
        "tokens": token_sum,
        "windows": count,
        "preview": preview,
        "episode_id": batch[0]["episode_id"],
        "join_method": (row.get("join_method") or "").strip(),
        "verdict": verdict,
    }
    return batch, meta


def _episode_key(episode_id: str) -> str:
    return episode_id.rsplit("-w", 1)[0]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open_private(path) as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _split_counts(episodes: list[dict]) -> tuple[int, int, int]:
    episodes_n = len(episodes)
    windows = sum(int(episode.get("windows") or 0) for episode in episodes)
    tokens = sum(int(episode.get("tokens") or 0) for episode in episodes)
    return episodes_n, windows, tokens


def _per_repo(episodes: list[dict]) -> dict:
    table: dict[str, dict] = {}
    for episode in episodes:
        _bump(table, episode.get("repo") or "", 1, int(episode.get("windows") or 0), int(episode.get("tokens") or 0))
    return table


def _pr_set(metas: list[dict]) -> set[tuple[str, int]]:
    return {(meta.get("repo") or "", int(meta.get("pr"))) for meta in metas}


def _id_set(metas: list[dict]) -> set[str]:
    return {str(meta.get("key") or "") for meta in metas}


def assert_holdout_disjoint(
    trained: list[dict], held: list[dict], train_records: list[dict], hold_records: list[dict],
) -> None:
    """Holdout and train share no pull request and no episode id."""
    overlap_pr = _pr_set(trained) & _pr_set(held)
    overlap_ep = _id_set(trained) & _id_set(held)
    train_rec_pr = {(record.get("repo") or "", record.get("pr")) for record in train_records}
    hold_rec_pr = {(record.get("repo") or "", record.get("pr")) for record in hold_records}
    train_rec_ep = {_episode_key(record["episode_id"]) for record in train_records}
    hold_rec_ep = {_episode_key(record["episode_id"]) for record in hold_records}
    if overlap_pr or overlap_ep or (train_rec_pr & hold_rec_pr) or (train_rec_ep & hold_rec_ep):
        raise AssertionError(
            "holdout overlaps train "
            f"prs={len(overlap_pr)} episodes={len(overlap_ep)} "
            f"record_prs={len(train_rec_pr & hold_rec_pr)} "
            f"record_episodes={len(train_rec_ep & hold_rec_ep)}"
        )


def apply_splits(records: list[dict], metas: list[dict], stats: dict, seed: int, cap: int, fraction: float) -> tuple[list[dict], list[dict]]:
    """Builder holdout by merge date, then a seeded conference-os sample under the token cap."""
    builders = [meta for meta in metas if meta.get("role") == "builder"]
    held_keys = holdout_pr_keys(builders, fraction)
    held = [meta for meta in builders if (meta.get("repo") or "", int(meta.get("pr"))) in held_keys]
    pool = [meta for meta in builders if (meta.get("repo") or "", int(meta.get("pr"))) not in held_keys]
    trained = sample_training_episodes(pool, cap, seed)
    trained_keys = {meta["key"] for meta in trained}
    held_episode_keys = {meta["key"] for meta in held}
    train_records = [record for record in records if _episode_key(record["episode_id"]) in trained_keys]
    hold_records = [record for record in records if _episode_key(record["episode_id"]) in held_episode_keys]
    assert_holdout_disjoint(trained, held, train_records, hold_records)
    unsampled = [meta for meta in pool if meta["key"] not in trained_keys]
    dates = sorted(meta.get("merged_at") or "" for meta in held if meta.get("merged_at"))
    stats["seed"] = seed
    stats["train_token_cap"] = cap
    stats["holdout_fraction"] = fraction
    stats["holdout_cutoff"] = dates[0] if dates else ""
    stats["builder_prs"] = len({(meta.get("repo"), meta.get("pr")) for meta in builders})
    stats["holdout_prs"] = len(held_keys)
    stats["holdout_episodes"], stats["holdout_windows"], stats["holdout_tokens"] = _split_counts(held)
    stats["pool_episodes"], stats["pool_windows"], stats["pool_tokens"] = _split_counts(pool)
    stats["train_episodes"], stats["train_windows"], stats["train_tokens"] = _split_counts(trained)
    stats["unsampled_episodes"], stats["unsampled_windows"], stats["unsampled_tokens"] = _split_counts(unsampled)
    stats["train_per_repo"] = _per_repo(trained)
    stats["holdout_per_repo"] = _per_repo(held)
    stats["overlap_prs"] = 0
    stats["overlap_episodes"] = 0
    return train_records, hold_records


def write_role_examples(path: Path, metas: list[dict], seed: int, per_role: int = 10) -> None:
    """Ten episode previews per role. The text is already redacted."""
    rng = random.Random(seed)
    lines = [f"seed {seed}", ""]
    for role in ("builder", "reviewer", "other"):
        group = [meta for meta in metas if meta.get("role") == role]
        lines.append(f"role {role} episodes {len(group)}")
        picks = list(group)
        rng.shuffle(picks)
        for meta in picks[:per_role]:
            preview = (meta.get("preview") or "").replace("\t", " ").replace("\n", " ")
            lines.append(f"{meta.get('episode_id')}\t{preview[:120]}")
        lines.append("")
    text = "\n".join(lines)
    if residual_names(text):
        text = f"seed {seed}\npreviews withheld; residual pattern after redaction\n"
    with open_private(path) as handle:
        handle.write(text)


def _join_cross(metas: list[dict]) -> dict:
    table: dict[str, dict] = {}
    for meta in metas:
        key = "|".join((
            meta.get("join_method") or "?",
            meta.get("role") or "?",
            meta.get("repo") or "?",
            meta.get("vendor") or "?",
        ))
        _bump(table, key, 1, int(meta.get("windows") or 0), int(meta.get("tokens") or 0))
    return table


def _fold_validation(stats: dict, path: Path | None, max_episode: int) -> None:
    if path is None or not path.exists() or path.stat().st_size == 0:
        return
    checked = validate_jsonl(path, max_episode)
    stats["secret_hit_total"] += checked["secret_hit_total"]
    stats["bad_json"] += checked["bad_json"]
    for key, value in checked["schema_errors"].items():
        stats["schema_errors"][key] = stats["schema_errors"].get(key, 0) + value


def run(csv_path: Path, prs_dir: Path, out: Path, stats_path: Path, host: str,
        max_tool: int, max_episode: int, train_path: Path | None = None,
        holdout_path: Path | None = None, cache_dir: Path | None = None,
        seed: int = SAMPLE_SEED, cap: int = TRAIN_TOKEN_CAP,
        fraction: float = HOLDOUT_FRACTION, examples_path: Path | None = None,
        negatives_path: Path | None = None, assessor_path: Path | None = None,
        all_hosts: bool = False, states: tuple[str, ...] = ("MERGED",),
        corpus_version: str = "v1") -> int:
    outputs = [out]
    for extra in (train_path, holdout_path, examples_path, negatives_path, assessor_path):
        if extra is not None:
            outputs.append(extra)
    for target in outputs:
        if inside_git(target) or not output_allowed(target):
            print("refusing: output must be outside git and under the trace root or temp dir", file=sys.stderr)
            return 2
    if cache_dir is not None and not output_allowed(cache_dir):
        print("refusing: issue cache must be under the trace root or temp dir", file=sys.stderr)
        return 2
    stats = _empty_stats()
    stats["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats["seed"] = seed
    stats["train_token_cap"] = cap
    stats["holdout_fraction"] = fraction
    stats["corpus_version"] = corpus_version
    rows = select_rows(csv_path, host, states=states, all_hosts=all_hosts)
    merged_rows = [row for row in rows if row.get("pr_state") == "MERGED"]
    closed_rows = [row for row in rows if row.get("pr_state") == "CLOSED"]
    stats["selected"] = len(merged_rows)
    index = load_prs(prs_dir)
    schema = load_schema()
    store = IssueStore(cache_dir) if cache_dir is not None else None
    records: list[dict] = []
    metas: list[dict] = []
    negative_records: list[dict] = []
    negative_metas: list[dict] = []
    closed_stats = _empty_stats()

    def _pr_for(row: dict) -> dict | None:
        try:
            return index.get((row.get("repo") or "", int(row["pr"])))
        except (TypeError, ValueError):
            return None

    for n, row in enumerate(merged_rows, start=1):
        batch, meta = convert_row(row, _pr_for(row), stats, schema, max_tool, max_episode, store, "merged")
        records.extend(batch)
        if meta is not None:
            metas.append(meta)
        if n % 25 == 0:
            print(
                f"progress {n}/{len(merged_rows)} windows={len(records)} episodes={stats['usable_episodes']}",
                file=sys.stderr,
            )
    for n, row in enumerate(closed_rows, start=1):
        batch, meta = convert_row(
            row, _pr_for(row), closed_stats, schema, max_tool, max_episode, store, "closed_unmerged",
        )
        if meta is not None and meta.get("role") == "builder":
            negative_records.extend(batch)
            negative_metas.append(meta)
        if n % 25 == 0:
            print(f"closed {n}/{len(closed_rows)} negative_episodes={len(negative_metas)}", file=sys.stderr)
    _write_jsonl(out, records)
    if train_path is not None and holdout_path is not None:
        train_records, hold_records = apply_splits(records, metas, stats, seed, cap, fraction)
        _write_jsonl(train_path, train_records)
        _write_jsonl(holdout_path, hold_records)
    if negatives_path is not None:
        _write_jsonl(negatives_path, negative_records)
    assessor_metas = [meta for meta in metas if meta.get("role") == "reviewer" and meta.get("verdict")]
    if assessor_path is not None:
        assessor_keys = {meta["key"] for meta in assessor_metas}
        assessor_records = [record for record in records if _episode_key(record["episode_id"]) in assessor_keys]
        _write_jsonl(assessor_path, assessor_records)
        stats["assessor_episodes"] = len(assessor_metas)
        stats["assessor_windows"] = sum(int(meta.get("windows") or 0) for meta in assessor_metas)
        stats["assessor_tokens"] = sum(int(meta.get("tokens") or 0) for meta in assessor_metas)
    if examples_path is not None:
        write_role_examples(examples_path, metas, seed)
    if corpus_version != "v1":
        stats["join_cross"] = _join_cross(metas + negative_metas)
        stats["join_tally"] = tally_join(csv_path)
        stats["negative_episodes"] = len(negative_metas)
        stats["negative_windows"] = sum(int(meta.get("windows") or 0) for meta in negative_metas)
        stats["negative_tokens"] = sum(int(meta.get("tokens") or 0) for meta in negative_metas)
        stats["negative_per_repo"] = _per_repo(negative_metas)
    file_stats = validate_jsonl(out, max_episode) if records else {
        "records": 0, "bad_json": 0, "schema_errors": {}, "secret_hit_total": 0,
    }
    stats["file_records"] = file_stats["records"]
    stats["bad_json"] = file_stats["bad_json"]
    stats["schema_errors"] = file_stats["schema_errors"]
    stats["secret_hit_total"] = file_stats["secret_hit_total"]
    for extra in (train_path, holdout_path, negatives_path, assessor_path):
        _fold_validation(stats, extra, max_episode)
    text = render_stats(stats)
    leaked = drop_if_residual({"task": text})[1]
    if leaked:
        print(f"refusing to write stats; residual patterns: {','.join(leaked)}", file=sys.stderr)
        return 1
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(text, encoding="utf-8")
    print(
        f"episodes={stats['usable_episodes']} windows={stats['windows']} "
        f"secret_hits={stats['secret_hit_total']} schema_errors={sum(stats['schema_errors'].values())} "
        f"train_tokens={stats.get('train_tokens', 0)} holdout_tokens={stats.get('holdout_tokens', 0)}",
        file=sys.stderr,
    )
    if stats["secret_hit_total"] or stats["bad_json"] or stats["schema_errors"]:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 training/historical/extract.py",
        usage=(
            "python3 training/historical/extract.py --csv PATH --prs-dir PATH "
            "--out PATH --stats PATH [--train PATH --holdout PATH]"
        ),
        description="Convert merged on-host sessions into historical SFT JSONL.",
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--prs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--train", type=Path)
    parser.add_argument("--holdout", type=Path)
    parser.add_argument("--examples", type=Path)
    parser.add_argument("--issue-cache", type=Path)
    parser.add_argument("--host", default="MacBook-Pro-4")
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
    parser.add_argument("--train-token-cap", type=int, default=TRAIN_TOKEN_CAP)
    parser.add_argument("--holdout-fraction", type=float, default=HOLDOUT_FRACTION)
    parser.add_argument("--max-tool-tokens", type=int, default=TOOL_TOKEN_LIMIT)
    parser.add_argument("--max-episode-tokens", type=int, default=EPISODE_TOKEN_LIMIT)
    parser.add_argument("--negatives", type=Path)
    parser.add_argument("--assessor", type=Path)
    parser.add_argument("--all-hosts", action="store_true")
    parser.add_argument("--states", default="MERGED")
    parser.add_argument("--corpus-version", default="v1")
    args = parser.parse_args(argv)
    if (args.train is None) != (args.holdout is None):
        print("refusing: pass both --train and --holdout, or neither", file=sys.stderr)
        return 2
    states = tuple(part.strip() for part in args.states.split(",") if part.strip())
    return run(
        args.csv, args.prs_dir, args.out, args.stats, args.host,
        args.max_tool_tokens, args.max_episode_tokens,
        train_path=args.train, holdout_path=args.holdout, cache_dir=args.issue_cache,
        seed=args.seed, cap=args.train_token_cap, fraction=args.holdout_fraction,
        examples_path=args.examples, negatives_path=args.negatives, assessor_path=args.assessor,
        all_hosts=args.all_hosts, states=states, corpus_version=args.corpus_version,
    )


if __name__ == "__main__":
    sys.exit(main())
