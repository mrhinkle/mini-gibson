#!/usr/bin/env python3
"""history_inventory.py — metadata-only inventory of agent sessions already on disk.

The flight recorder captures runs from now on. This answers the earlier question:
how many Grok / Codex / Claude Code runs against Gibson, ConferenceOS and Chatterbuilt
already exist in the CLIs' own session stores, and which ones can be joined to a PR outcome?

Reads (never writes, never copies content):
  ~/.grok/sessions/<urlencoded cwd>/<session>/{summary.json,updates.jsonl}
  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
  ~/.claude/projects/<slug>/<session>.jsonl

Emits one CSV row per session: vendor, host, session id, cwd, repo, branch, issue guess,
start time, tool-call count, model. No prompts, tool arguments or outputs leave the source files.
Output must go to the private trace root (outside any git worktree). Stdlib only.

  python3 history_inventory.py --out ~/gibson-traces/inventory/sessions.$(hostname -s).csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

REPOS = (("the-gibson", re.compile(r"gibson", re.I)),
         ("conference-os", re.compile(r"conference-os|/cos-|cos-wt|/lanes/cos", re.I)),
         ("chatterbuilt", re.compile(r"chatterbuilt", re.I)))
ISSUE_RE = re.compile(r"(?:lane|wt|issue|feat|fix|prep|pr|cos|cb|gibson)[-_/#]?(\d{2,5})(?!\d)", re.I)
HOME = Path.home()


def repo_of(*texts: str) -> str:
    for t in texts:
        for name, rx in REPOS:
            if t and rx.search(t):
                return name
    return ""


def issue_of(*texts: str) -> str:
    for t in texts:
        m = ISSUE_RE.search(t or "")
        if m:
            return m.group(1)
    return ""


def count_lines(path: Path, needles: tuple[str, ...], exclude: tuple[str, ...] = ()) -> int:
    n = 0
    try:
        with path.open("rb") as fh:
            for line in fh:
                if any(x.encode() in line for x in needles) and not any(x.encode() in line for x in exclude):
                    n += 1
    except OSError:
        pass
    return n


def first_json(path: Path, pred, limit: int = 200):
    try:
        with path.open("rb") as fh:
            for i, line in enumerate(fh):
                if i >= limit:
                    break
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if pred(obj):
                    return obj
    except OSError:
        pass
    return None


def grok_rows(root: Path):
    if not root.is_dir():
        return
    for cwd_dir in root.iterdir():
        if not cwd_dir.is_dir():
            continue
        cwd = urllib.parse.unquote(cwd_dir.name)
        for sess in cwd_dir.iterdir():
            summ = sess / "summary.json"
            if not summ.is_file():
                continue
            try:
                s = json.loads(summ.read_text(errors="replace"))
            except ValueError:
                s = {}
            cwd2 = (s.get("info") or {}).get("cwd") or cwd
            repo = repo_of(cwd2)
            upd = sess / "updates.jsonl"
            tools = count_lines(upd, ('"sessionUpdate":"tool_call"',)) if repo else -1
            yield dict(vendor="grok", session_id=sess.name, cwd=cwd2, repo=repo, branch="",
                       issue=issue_of(cwd2), started=s.get("created_at", ""), ended=s.get("updated_at", ""),
                       tool_calls=tools, model=s.get("current_model_id", ""), kind=s.get("session_kind", ""),
                       bytes=upd.stat().st_size if upd.exists() else 0, path=str(sess))


def codex_rows(root: Path):
    if not root.is_dir():
        return
    for f in root.rglob("rollout-*.jsonl"):
        meta = first_json(f, lambda o: o.get("type") == "session_meta", 5) or {}
        p = meta.get("payload") or {}
        git = p.get("git") or {}
        cwd = p.get("cwd", "")
        branch = git.get("branch", "") if isinstance(git, dict) else ""
        repo = repo_of(cwd, branch, git.get("repository_url", "") if isinstance(git, dict) else "")
        tools = count_lines(f, ('"type":"function_call"', '"type":"custom_tool_call"', '"type":"local_shell_call"'),
                            ('_output"',)) if repo else -1
        yield dict(vendor="codex", session_id=p.get("id", f.stem), cwd=cwd, repo=repo, branch=branch,
                   issue=issue_of(branch, cwd), started=p.get("timestamp", ""), ended="",
                   tool_calls=tools, model=p.get("model", "") or p.get("model_provider", ""),
                   kind=p.get("originator", ""), bytes=f.stat().st_size, path=str(f))


def claude_rows(root: Path):
    if not root.is_dir():
        return
    for f in root.glob("*/*.jsonl"):
        o = first_json(f, lambda o: bool(o.get("cwd")), 50) or {}
        cwd, branch = o.get("cwd", ""), o.get("gitBranch", "") or ""
        repo = repo_of(cwd, branch)
        tools = count_lines(f, ('"type":"tool_use"',)) if repo else -1
        yield dict(vendor="claude", session_id=f.stem, cwd=cwd, repo=repo, branch=branch,
                   issue=issue_of(branch, cwd), started=o.get("timestamp", ""), ended="",
                   tool_calls=tools, model="", kind="sidechain" if o.get("isSidechain") else "",
                   bytes=f.stat().st_size, path=str(f))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--all", action="store_true", help="include sessions not tied to the three repos")
    a = ap.parse_args(argv)
    out = Path(a.out).expanduser()
    if subprocess.run(["git", "-C", str(out.parent), "rev-parse"], capture_output=True).returncode == 0:
        print(f"refusing: {out.parent} is inside a git worktree", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname().split(".")[0]
    fields = ["host", "vendor", "session_id", "repo", "issue", "branch", "started", "ended",
              "tool_calls", "model", "kind", "bytes", "cwd", "path"]
    n = kept = 0
    old = os.umask(0o077)
    try:
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for gen in (grok_rows(HOME / ".grok/sessions"), codex_rows(HOME / ".codex/sessions"),
                        claude_rows(HOME / ".claude/projects")):
                for r in gen:
                    n += 1
                    if r["repo"] or a.all:
                        kept += 1
                        w.writerow({"host": host, **r})
    finally:
        os.umask(old)
    print(f"{host}: scanned {n} sessions, wrote {kept} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
