"""Join one agent session to one pull request.

Methods run in order. The first method that finds a pull request wins.
More than one pull request is ambiguous and later methods are not tried.
A commit or an issue that matches several pull requests still joins when
exactly one of those pull requests is MERGED (stacked or superseded
pull requests share commits and issues). The join methods for that case
are commit-merged-unique and issue-merged-unique. Any other ambiguous
set stays unjoined.

(a) branch name equals the pull request head branch.
(b) commit SHAs in the session's own tool output.
(c) an issue number from the worktree path, or from the prompt when the
    path has none. The pull request's closingIssuesReferences must contain it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPOS = ("conference-os", "chatterbuilt", "the-gibson")
JOIN_BRANCH = "branch"
JOIN_COMMIT = "commit"
JOIN_ISSUE = "issue"
JOIN_COMMIT_MERGED = "commit-merged-unique"
JOIN_ISSUE_MERGED = "issue-merged-unique"
MAX_COMMIT_SHAS = 12

# Worktree names whose number is the issue: lane-N, cos-N, wt-N, and the
# cb-lane / cos-lane prefixes used on this machine.
_PATH_ISSUE = re.compile(
    r"(?:^|/)(?:cb-lane|cos-lane|lane|wt|cos|gibson|cb)-(\d{2,5})(?!\d)",
    re.IGNORECASE,
)
_ISSUE_WORD = re.compile(r"(?i)\bissues?\s*#\s*(\d{2,5})\b")
_HASH_NUM = re.compile(r"(?<![A-Za-z0-9_])#(\d{2,5})\b")
_USER_QUERY = re.compile(r"<user_query>(.*?)</user_query>", re.IGNORECASE | re.DOTALL)
_REPO_PROSE = re.compile(r"(?i)\b(conference-os|the-gibson|chatterbuilt)\b")
# git commit prints "[branch sha] subject". A line that is only a 40-char
# hex is rev-parse HEAD. git log lines are neither, so they are not harvested.
_COMMIT_BRACKET = re.compile(r"\[(?P<branch>[^\s\[\]]{1,120}) (?P<sha>[0-9a-f]{7,40})\]")
_BARE_SHA = re.compile(r"(?m)^[ \t]*([0-9a-f]{40})[ \t]*$")


def _unique(numbers: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for number in numbers:
        if number in seen:
            continue
        seen.add(number)
        out.append(number)
    return out


def repo_hint(*texts: str) -> str:
    """Repo named by a worktree path. Empty when the path does not say."""
    blob = " ".join(text or "" for text in texts).lower()
    if "chatterbuilt" in blob or "cb-lane" in blob or "/cb-" in blob:
        return "chatterbuilt"
    if "conference-os" in blob or "cos-lane" in blob or "/cos-" in blob or "nhcos" in blob:
        return "conference-os"
    if "gibson" in blob:
        return "the-gibson"
    return ""


def issue_numbers_from_path(cwd: str) -> list[int]:
    return _unique(int(match) for match in _PATH_ISSUE.findall(cwd or ""))


def prompt_text(user_texts: list[str]) -> str:
    """The session's own query. Rules wrapped around a user_query do not count."""
    raw = "\n".join(user_texts)
    blocks = _USER_QUERY.findall(raw)
    if blocks:
        return "\n".join(blocks)
    return raw


def issue_numbers_from_prompt(text: str) -> list[int]:
    blob = prompt_text([text])
    found = [int(match) for match in _ISSUE_WORD.findall(blob)]
    found.extend(int(match) for match in _HASH_NUM.findall(blob))
    return _unique(found)


def repo_from_prompt(text: str) -> str:
    found = []
    for match in _REPO_PROSE.findall(prompt_text([text])):
        name = match.lower()
        if name not in found:
            found.append(name)
    if len(found) == 1:
        return found[0]
    return ""


def issues_for_join(cwd: str, user_text: str) -> list[int]:
    """Path issue when the worktree names exactly one. Otherwise the prompt."""
    from_path = issue_numbers_from_path(cwd)
    if len(from_path) == 1:
        return from_path
    if len(from_path) > 1:
        return from_path
    return issue_numbers_from_prompt(user_text)


def commit_shas_from_tool_output(text: str) -> list[str]:
    """SHAs the session's tool output shows it created or resolved as HEAD."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _COMMIT_BRACKET.finditer(text or ""):
        sha = match.group("sha")
        if sha not in seen:
            seen.add(sha)
            found.append(sha)
    for match in _BARE_SHA.finditer(text or ""):
        sha = match.group(1)
        if sha not in seen:
            seen.add(sha)
            found.append(sha)
    return found


def _parts_text(content) -> str:
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
                    bits.append(_parts_text(item.get("content")))
        return "\n".join(bits)
    if isinstance(content, dict):
        if "text" in content:
            return str(content.get("text") or "")
        if "content" in content:
            return _parts_text(content.get("content"))
        return ""
    return str(content)


def _iter_jsonl(path: Path):
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


def _consume(obj: dict, vendor: str, tool_parts: list[str], user_parts: list[str]) -> None:
    """Pull tool output and user text out of one session record."""
    if vendor == "grok" and obj.get("type") in ("user", "tool_result", "assistant"):
        kind = obj.get("type")
        if kind == "user":
            user_parts.append(_parts_text(obj.get("content")))
        elif kind == "tool_result":
            tool_parts.append(_parts_text(obj.get("content")))
        return
    if obj.get("type") == "response_item":
        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            return
        ptype = payload.get("type")
        if ptype == "message" and payload.get("role") == "user":
            user_parts.append(_parts_text(payload.get("content")))
        elif ptype in ("function_call_output", "custom_tool_call_output", "local_shell_call_output", "tool_call_output"):
            out = payload.get("output")
            if out is None:
                out = payload.get("aggregated_output")
            tool_parts.append(_parts_text(out))
        return
    if obj.get("type") == "item.completed":
        item = obj.get("item") or {}
        if isinstance(item, dict) and item.get("type") == "command_execution":
            tool_parts.append(_parts_text(item.get("aggregated_output")))
        return
    kind = obj.get("type")
    message = obj.get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if kind == "user":
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    tool_parts.append(_parts_text(block.get("content")))
                elif block.get("type") == "text":
                    user_parts.append(str(block.get("text") or ""))
        elif isinstance(content, str):
            user_parts.append(content)
    elif kind == "tool_result":
        tool_parts.append(_parts_text(obj.get("content")))


def collect_signals(path: Path, vendor: str, cwd: str) -> dict:
    """Read a session once. Returns shas, issue numbers, and a prompt repo."""
    tool_parts: list[str] = []
    user_parts: list[str] = []
    files: list[Path]
    if path.is_dir():
        chat = path / "chat_history.jsonl"
        files = [chat] if chat.is_file() else []
        vendor = "grok"
    else:
        files = [path] if path.is_file() else []
    for fp in files:
        try:
            rows = _iter_jsonl(fp)
        except OSError:
            continue
        for obj in rows:
            _consume(obj, vendor, tool_parts, user_parts)
    user_text = "\n".join(user_parts)
    shas = commit_shas_from_tool_output("\n".join(tool_parts))
    return {
        "shas": shas,
        "issues": issues_for_join(cwd, user_text),
        "prompt_repo": repo_from_prompt(user_text),
        "sha_overflow": len(shas) > MAX_COMMIT_SHAS,
    }


class PrCatalog:
    """Branch and closing-issue indexes over the three repos."""

    def __init__(self, prs_by_repo: dict[str, list[dict]]):
        self.by_key: dict[tuple[str, int], dict] = {}
        self.by_branch: dict[tuple[str, str], list[tuple[str, int]]] = {}
        self.by_issue: dict[tuple[str, int], list[tuple[str, int]]] = {}
        for repo, prs in prs_by_repo.items():
            for pr in prs:
                number = pr.get("number")
                if not isinstance(number, int):
                    continue
                key = (repo, number)
                self.by_key[key] = pr
                branch = (pr.get("headRefName") or "").strip()
                if branch:
                    self.by_branch.setdefault((repo, branch), []).append(key)
                for ref in pr.get("closingIssuesReferences") or []:
                    if not isinstance(ref, dict) or not isinstance(ref.get("number"), int):
                        continue
                    ref_repo = ((ref.get("repository") or {}).get("name")) or repo
                    if ref_repo != repo:
                        continue
                    self.by_issue.setdefault((repo, ref["number"]), []).append(key)

    def _repos(self, repo: str) -> tuple[str, ...]:
        if repo in REPOS:
            return (repo,)
        return REPOS

    def branch_keys(self, repo: str, branch: str) -> list[tuple[str, int]]:
        branch = (branch or "").strip()
        if not branch:
            return []
        found: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for name in self._repos(repo):
            for key in self.by_branch.get((name, branch), []):
                if key not in seen:
                    seen.add(key)
                    found.append(key)
        return found

    def issue_keys(self, repo: str, numbers: list[int]) -> list[tuple[str, int]]:
        found: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for name in self._repos(repo):
            for number in numbers:
                for key in self.by_issue.get((name, number), []):
                    if key not in seen:
                        seen.add(key)
                        found.append(key)
        return found


def _unique_keys(keys: list[tuple[str, int]]) -> list[tuple[str, int]]:
    uniq: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            uniq.append(key)
    return uniq


def _merged_unique(
    keys: list[tuple[str, int]],
    pr_states: dict[tuple[str, int], str] | None,
) -> tuple[str, int] | None:
    """The one MERGED key, when the candidate set has exactly one."""
    if not pr_states:
        return None
    merged = [key for key in _unique_keys(keys) if pr_states.get(key) == "MERGED"]
    if len(merged) == 1:
        return merged[0]
    return None


def decide_join(
    branch_keys: list[tuple[str, int]],
    commit_keys: list[tuple[str, int]],
    issue_keys: list[tuple[str, int]],
    *,
    commit_attempted: bool,
    issue_attempted: bool,
    pr_states: dict[tuple[str, int], str] | None = None,
) -> dict:
    """Pick the winning method. Keys are (repo, pr_number)."""

    def one(keys: list[tuple[str, int]]) -> tuple[str, int] | None:
        uniq = _unique_keys(keys)
        if len(uniq) == 1:
            return uniq[0]
        return None

    def finish(method: str, picked: tuple[str, int]) -> dict:
        return {"join_method": method, "reason": "", "repo": picked[0], "pr": picked[1]}

    if branch_keys:
        picked = one(branch_keys)
        if picked is not None:
            return finish(JOIN_BRANCH, picked)
        return {"join_method": "", "reason": "ambiguous_branch", "repo": "", "pr": ""}
    if commit_attempted:
        if len(_unique_keys(commit_keys)) > 1:
            picked = _merged_unique(commit_keys, pr_states)
            if picked is not None:
                return finish(JOIN_COMMIT_MERGED, picked)
            return {"join_method": "", "reason": "ambiguous_commit", "repo": "", "pr": ""}
        picked = one(commit_keys)
        if picked is not None:
            return finish(JOIN_COMMIT, picked)
    if issue_attempted:
        if len(_unique_keys(issue_keys)) > 1:
            picked = _merged_unique(issue_keys, pr_states)
            if picked is not None:
                return finish(JOIN_ISSUE_MERGED, picked)
            return {"join_method": "", "reason": "ambiguous_issue", "repo": "", "pr": ""}
        picked = one(issue_keys)
        if picked is not None:
            return finish(JOIN_ISSUE, picked)
    if not commit_attempted and not issue_attempted and not branch_keys:
        return {"join_method": "", "reason": "no_signal", "repo": "", "pr": ""}
    return {"join_method": "", "reason": "no_match", "repo": "", "pr": ""}
