"""Inventory live sessions and join each one to a pull request.

Writes ~/gibson-traces/inventory/sessions.v2.csv. Does not write inside a
git worktree. Mini session files must already be copied under the trace root.

Usage:
  python3 training/historical/build_v2.py --out PATH --prs-dir PATH --cache PATH
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from training.historical.join import (  # noqa: E402
    MAX_COMMIT_SHAS,
    REPOS,
    PrCatalog,
    collect_signals,
    decide_join,
    issue_numbers_from_path,
    repo_hint,
)
from training.historical.prs_index import load_catalog, write_catalog  # noqa: E402

FIELDS = [
    "host", "vendor", "session_id", "repo", "issue", "branch", "started", "ended",
    "tool_calls", "model", "kind", "bytes", "cwd", "path", "pr", "pr_state", "join",
    "join_method",
]


def _load_history():
    path = _REPO_ROOT / "scripts" / "data" / "history_inventory.py"
    spec = importlib.util.spec_from_file_location("history_inventory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _under_trace(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    root = (Path.home() / "gibson-traces").resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def _keep(row: dict) -> bool:
    if row.get("repo"):
        return True
    return bool(issue_numbers_from_path(row.get("cwd") or ""))


def _normalize_row(row: dict, host: str) -> dict:
    cwd = row.get("cwd") or ""
    repo = row.get("repo") or repo_hint(cwd)
    issues = issue_numbers_from_path(cwd)
    issue = issues[0] if len(issues) == 1 else (row.get("issue") or "")
    if issues and str(issue) not in {str(n) for n in issues}:
        issue = ""
    out = dict(row)
    out["host"] = host
    out["repo"] = repo
    out["issue"] = str(issue) if issue else ""
    out["branch"] = (row.get("branch") or "").strip()
    return out


def scan_host(history, host: str, grok: Path, codex: Path, claude: Path) -> list[dict]:
    rows = []
    for gen, vendor_root in (
        (history.grok_rows(grok), "grok"),
        (history.codex_rows(codex), "codex"),
        (history.claude_rows(claude), "claude"),
    ):
        del vendor_root
        for raw in gen:
            row = _normalize_row(raw, host)
            if _keep(row):
                rows.append(row)
    return rows


def _gh_env() -> dict:
    env = os.environ.copy()
    env["GH_FORCE_TTY"] = "0"
    env["NO_COLOR"] = "1"
    env.pop("CLICOLOR_FORCE", None)
    return env


def lookup_commit(repo: str, sha: str, cache_dir: Path, retries: int = 2) -> list[tuple[str, int]]:
    """PRs that contain this commit. Empty when GitHub has no such commit."""
    dest = cache_dir / "sha-v2" / f"{repo}-{sha}.json"
    if dest.is_file():
        try:
            data = json.loads(dest.read_text(encoding="utf-8"))
            return [(repo, number) for number in data.get("numbers") or []]
        except (OSError, json.JSONDecodeError):
            pass
    proc = subprocess.run(
        [
            "gh", "api",
            "-H", "Accept: application/vnd.github+json",
            f"repos/The-AIE/{repo}/commits/{sha}/pulls",
        ],
        capture_output=True,
        text=True,
        timeout=45,
        env=_gh_env(),
    )
    numbers: list[int] = []
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("number"), int):
                    numbers.append(item["number"])
    elif proc.returncode != 0 and retries > 0 and "rate limit" in (proc.stderr or "").lower():
        time.sleep(20)
        return lookup_commit(repo, sha, cache_dir, retries - 1)
    err = proc.stderr or ""
    cacheable = proc.returncode == 0 or any(token in err for token in ("404", "422", "No commit"))
    if not cacheable:
        return [(repo, number) for number in numbers]
    dest.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(dest, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"numbers": numbers, "status": proc.returncode}, handle)
    return [(repo, number) for number in numbers]


def _apply(row: dict, decision: dict, catalog: PrCatalog) -> dict:
    method = decision["join_method"]
    reason = decision["reason"]
    if method:
        repo, number = decision["repo"], int(decision["pr"])
        pr = catalog.by_key.get((repo, number)) or {}
        row["repo"] = repo
        row["pr"] = str(number)
        row["pr_state"] = pr.get("state") or ""
        row["join"] = method
        row["join_method"] = method
        if not row.get("issue"):
            for ref in pr.get("closingIssuesReferences") or []:
                if isinstance(ref, dict) and isinstance(ref.get("number"), int):
                    row["issue"] = str(ref["number"])
                    break
    else:
        row["pr"] = ""
        row["pr_state"] = ""
        row["join"] = reason or "no_match"
        row["join_method"] = ""
    return row


def join_rows(rows: list[dict], catalog: PrCatalog, cache_dir: Path) -> dict:
    """Join in place. Returns reason and method counts."""
    reasons: dict[str, int] = {}
    methods: dict[str, int] = {}
    pr_states = {key: (pr.get("state") or "") for key, pr in catalog.by_key.items()}
    pending = []
    for index, row in enumerate(rows, start=1):
        keys = catalog.branch_keys(row.get("repo") or "", row.get("branch") or "")
        if row.get("branch") and keys:
            decision = decide_join(
                keys, [], [], commit_attempted=False, issue_attempted=False, pr_states=pr_states,
            )
            _apply(row, decision, catalog)
            bucket = methods if decision["join_method"] else reasons
            bucket[decision["join_method"] or decision["reason"]] = bucket.get(
                decision["join_method"] or decision["reason"], 0
            ) + 1
            continue
        pending.append(row)
        if index % 500 == 0:
            print(f"branch pass {index}/{len(rows)}", file=sys.stderr)
    print(f"branch joined or ambiguous {len(rows) - len(pending)}; reading {len(pending)} sessions", file=sys.stderr)

    lookups: set[tuple[str, str]] = set()
    for n, row in enumerate(pending, start=1):
        signals = collect_signals(Path(row.get("path") or ""), row.get("vendor") or "", row.get("cwd") or "")
        if not row.get("repo") and signals["prompt_repo"]:
            row["repo"] = signals["prompt_repo"]
        row["_shas"] = signals["shas"]
        row["_issues"] = signals["issues"]
        row["_overflow"] = signals["sha_overflow"]
        if signals["issues"] and not row.get("issue") and len(signals["issues"]) == 1:
            row["issue"] = str(signals["issues"][0])
        if not signals["sha_overflow"]:
            repos = (row["repo"],) if row.get("repo") in REPOS else REPOS
            for sha in signals["shas"][:MAX_COMMIT_SHAS]:
                for repo in repos:
                    lookups.add((repo, sha))
        if n % 100 == 0:
            print(f"signals {n}/{len(pending)} lookups {len(lookups)}", file=sys.stderr)

    resolved: dict[tuple[str, str], list[tuple[str, int]]] = {}
    print(f"commit lookups {len(lookups)}", file=sys.stderr)
    if lookups:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(lookup_commit, repo, sha, cache_dir): (repo, sha)
                for repo, sha in lookups
            }
            done = 0
            for future in as_completed(futures):
                key = futures[future]
                try:
                    resolved[key] = future.result()
                except (OSError, subprocess.TimeoutExpired, RuntimeError):
                    resolved[key] = []
                done += 1
                if done % 50 == 0:
                    print(f"lookups done {done}/{len(lookups)}", file=sys.stderr)

    for row in pending:
        commit_keys: list[tuple[str, int]] = []
        shas = row.get("_shas") or []
        overflow = bool(row.get("_overflow"))
        attempted = bool(shas) and not overflow
        if attempted:
            repos = (row["repo"],) if row.get("repo") in REPOS else REPOS
            for sha in shas[:MAX_COMMIT_SHAS]:
                for repo in repos:
                    commit_keys.extend(resolved.get((repo, sha), []))
        issues = [int(n) for n in (row.get("_issues") or [])]
        issue_keys = catalog.issue_keys(row.get("repo") or "", issues) if issues else []
        decision = decide_join(
            [],
            commit_keys,
            issue_keys,
            commit_attempted=attempted,
            issue_attempted=bool(issues),
            pr_states=pr_states,
        )
        if overflow and not decision["join_method"]:
            decision = dict(decision)
            if decision["reason"] == "no_signal":
                decision["reason"] = "sha_overflow"
        _apply(row, decision, catalog)
        bucket = methods if decision["join_method"] else reasons
        label = decision["join_method"] or decision["reason"]
        bucket[label] = bucket.get(label, 0) + 1
        row.pop("_shas", None)
        row.pop("_issues", None)
        row.pop("_overflow", None)
    return {"methods": methods, "reasons": reasons, "sessions": len(rows)}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not _under_trace(path):
        raise PermissionError("inventory CSV must stay under the trace root")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in FIELDS})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 training/historical/build_v2.py",
        usage=(
            "python3 training/historical/build_v2.py --out PATH --prs-dir PATH --cache PATH"
        ),
        description="Inventory on-disk sessions and join them to pull requests.",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prs-dir", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--mini", type=Path, default=Path.home() / "gibson-traces" / "raw" / "mini")
    parser.add_argument("--counts", type=Path, default=None)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args(argv)
    for target in (args.out, args.prs_dir, args.cache):
        if not _under_trace(target):
            print("refusing: outputs must stay under ~/gibson-traces", file=sys.stderr)
            return 2
    if not args.skip_fetch:
        counts = write_catalog(args.prs_dir, args.cache)
        print(f"prs {counts}", file=sys.stderr)
    catalog = PrCatalog(load_catalog(args.prs_dir))
    history = _load_history()
    host = socket.gethostname().split(".")[0]
    home = Path.home()
    rows = scan_host(
        history,
        host,
        home / ".grok" / "sessions",
        home / ".codex" / "sessions",
        home / ".claude" / "projects",
    )
    print(f"local sessions kept {len(rows)}", file=sys.stderr)
    if not args.local_only:
        mini = args.mini
        rows.extend(scan_host(
            history,
            "Marks-Mac-mini",
            mini / "grok-sessions",
            mini / "codex-sessions",
            mini / "claude-projects",
        ))
        print(f"sessions kept with mini {len(rows)}", file=sys.stderr)
    summary = join_rows(rows, catalog, args.cache)
    write_csv(args.out, rows)
    counts_path = args.counts or (args.out.parent / "join-v2-counts.json")
    if not _under_trace(counts_path):
        print("refusing: counts file must stay under ~/gibson-traces", file=sys.stderr)
        return 2
    payload = json.dumps(summary, sort_keys=True, indent=2)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(counts_path, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    print(json.dumps(summary, sort_keys=True), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
