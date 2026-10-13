"""Join one agent session to one pull request.

Methods run in order. The first method that finds a pull request wins.
More than one pull request is ambiguous and later methods are not tried.
A commit or an issue that matches several pull requests still joins when
exactly one of those pull requests is MERGED (stacked or superseded
pull requests share commits and issues). The join methods for that case
are commit-merged-unique and issue-merged-unique. Any other ambiguous
set stays unjoined.

(a) branch name equals the pull request head branch.
(a2) the header of the first user prompt (`prompt-header`). The header
    is the first non-empty line, or a line that starts with `TASK`.
    Exactly one branch on that line wins. Otherwise exactly one PR.
    Otherwise exactly one issue in one repo. Later PR numbers, including
    "do not enter lane-…", do not count. A header the catalog cannot
    resolve does not fall through to those later numbers.
(a3) the rest of that first user prompt declares a branch
    (`prompt-branch`) or a PR number (`prompt-pr`), when the header did
    not. Later tool output is not a declaration. A declared branch is
    resolved through the catalog. A declared PR number is that pull request.
(b) commit SHAs the session itself created: `git commit` prints
    `[branch sha]`, and `git rev-parse HEAD` counts only after that commit.
    A SHA from git log, git show, or rev-parse of another ref is ignored
    unless it is a candidate pull request's head or one of that pull
    request's commits.
(c) an issue number from the worktree path, or from the prompt when the
    path has none. The pull request's closingIssuesReferences must contain it.
(d) when a prompt or an issue matches two or more pull requests, each
    candidate is scored by edit coverage: the share of the session's
    successful edits that the pull request also changes. The highest
    score wins only when it is at least 0.5 and at least 0.2 above the
    runner-up (`coverage`). Equal scores prefer the candidate whose
    number appears on the header line. Jaccard is not used to choose.
A builder joined by a prompt or an issue must still have at least 30%
of its successful edits on that pull request. Below that the session
is unjoined (`no_file_overlap`). The confirm ratio is
|intersection| / |session edits|, not Jaccard: a merged pull request
is the union of every session plus the coordinator's commit, so a
session that edited a true subset scores a low Jaccard.
A read-only or reviewer session stays a reviewer. Joining it does not
make it a builder.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPOS = ("conference-os", "chatterbuilt", "the-gibson")
JOIN_BRANCH = "branch"
JOIN_PROMPT_HEADER = "prompt-header"
JOIN_PROMPT_BRANCH = "prompt-branch"
JOIN_PROMPT_PR = "prompt-pr"
JOIN_COMMIT = "commit"
JOIN_ISSUE = "issue"
JOIN_COMMIT_MERGED = "commit-merged-unique"
JOIN_ISSUE_MERGED = "issue-merged-unique"
JOIN_COVERAGE = "coverage"
MAX_COMMIT_SHAS = 12
# Candidate selection uses edit coverage, not Jaccard.
COVERAGE_PICK = 0.5
COVERAGE_MARGIN = 0.2
OVERLAP_CONFIRM = 0.3
_CONFIRM_METHODS = frozenset({
    JOIN_PROMPT_HEADER,
    JOIN_PROMPT_BRANCH,
    JOIN_PROMPT_PR,
    JOIN_ISSUE,
    JOIN_ISSUE_MERGED,
})

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
_ORG_REPO = r"The-AIE/(conference-os|chatterbuilt|the-gibson)"
_PROMPT_REPO = re.compile(_ORG_REPO, re.IGNORECASE)
_PROMPT_PR_HASH = re.compile(rf"(?i){_ORG_REPO}#(\d{{1,6}})\b")
_PROMPT_PR_PULL = re.compile(rf"(?i){_ORG_REPO}/pull/(\d{{1,6}})\b")
_PROMPT_PR_WORD = re.compile(r"(?i)\bPR\s*#\s*(\d{1,6})\b")
_BRANCH_TICK = re.compile(
    r"(?i)\b(?P<label>your\s+branch|integration\s+branch|base\s+branch|branch)\s+`(?P<name>[^`\n]+)`"
)
_BRANCH_BARE = re.compile(
    r"(?i)\b(?P<label>your\s+branch|branch)\s+(?P<name>[A-Za-z0-9][A-Za-z0-9._/-]{0,120})"
)
_WORKTREE = re.compile(
    r"(?i)\bworktree\s+`([^`\n]+)`|\bworktree\s+((?:/|~)[^\s,)]+)"
)
_PATCH_PATH = re.compile(
    r"\*\*\* (?:Update|Add|Delete) File:\s*(\S+)|\*\*\* Move to:\s*(\S+)"
)
_PATH_KEYS = ("file_path", "path", "target_file", "file", "filename")
# git commit prints "[branch sha] subject". A bare 40-char line is a SHA
# only when the command was `git rev-parse HEAD` after a commit in this session.
_COMMIT_BRACKET = re.compile(
    r"\[(?:detached HEAD|(?P<branch>[^\s\[\]]{1,120})) (?P<sha>[0-9a-f]{7,40})\]"
)
_BARE_SHA = re.compile(r"(?m)^[ \t]*([0-9a-f]{40})[ \t]*$")
_SHA_TOKEN = re.compile(r"\b([0-9a-f]{7,40})\b")
# `git -C <dir> commit` is still a commit. Quoted text is stripped before this runs.
_GIT_COMMIT_SEG = re.compile(r"(?i)(?:^|\s)git\b[^\n]*\bcommit\b")
_REV_PARSE_HEAD_SEG = re.compile(
    r"(?i)(?:^|\s)git\b[^\n]*\brev-parse\s+(?:--verify\s+)?HEAD\s*$"
)
_CALL_TYPES = {"function_call", "custom_tool_call", "local_shell_call", "tool_call"}
_OUTPUT_TYPES = {
    "function_call_output",
    "custom_tool_call_output",
    "local_shell_call_output",
    "tool_call_output",
}


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


def _unique_str(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _skip_branch_label(text: str, start: int, label: str) -> bool:
    """Integration and base branches are not the session's branch."""
    if "integration" in label.lower() or label.lower().startswith("base"):
        return True
    prefix = text[max(0, start - 24):start].lower()
    return "integration" in prefix


def _clean_branch_name(name: str) -> str:
    name = (name or "").strip().strip("`").rstrip(".,;:")
    if not name or name in {"main", "master", "origin/main", "origin/master"}:
        return ""
    if "/" not in name and "-" not in name:
        return ""
    return name


def _branch_names(text: str) -> list[str]:
    """Branch names in priority order. `your branch` hides other labels.

    More than one name at the winning priority means the text is not unique.
    Integration and base branches are skipped.
    """
    yours: list[str] = []
    others: list[str] = []
    for match in _BRANCH_TICK.finditer(text or ""):
        if _skip_branch_label(text, match.start(), match.group("label")):
            continue
        name = _clean_branch_name(match.group("name"))
        if not name:
            continue
        if "your" in match.group("label").lower():
            yours.append(name)
        else:
            others.append(name)
    yours = _unique_str(yours)
    if yours:
        return yours
    others = _unique_str(others)
    if others:
        return others
    bare: list[str] = []
    for match in _BRANCH_BARE.finditer(text or ""):
        if _skip_branch_label(text, match.start(), match.group("label")):
            continue
        name = _clean_branch_name(match.group("name"))
        if name:
            bare.append(name)
    return _unique_str(bare)


def _declared_branch(text: str) -> str:
    """The session branch named in the dispatch. Empty when it is not unique."""
    names = _branch_names(text)
    if len(names) == 1:
        return names[0]
    return ""


def _declared_worktree(text: str) -> str:
    for match in _WORKTREE.finditer(text or ""):
        path = (match.group(1) or match.group(2) or "").strip().rstrip(".,;")
        if path:
            return path
    return ""


def parse_prompt_declaration(text: str) -> dict:
    """Branch, PR, repo, and worktree named by the dispatch prompt.

    `PR #N` and `The-AIE/<repo>#N` are pull requests. `issue #N` is not.
    """
    text = text or ""
    repos: list[str] = []
    for match in _PROMPT_REPO.finditer(text):
        name = match.group(1).lower()
        if name not in repos:
            repos.append(name)
    bound: list[tuple[str, int]] = []
    seen_pairs: set[tuple[str, int]] = set()

    def add_bound(repo: str, number: int) -> None:
        key = (repo, number)
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        bound.append(key)

    for pattern in (_PROMPT_PR_HASH, _PROMPT_PR_PULL):
        for match in pattern.finditer(text):
            add_bound(match.group(1).lower(), int(match.group(2)))
    bound_numbers = {number for _, number in bound}
    loose: list[int] = []
    for match in _PROMPT_PR_WORD.finditer(text):
        number = int(match.group(1))
        if number not in bound_numbers:
            loose.append(number)
    repo = repos[0] if len(repos) == 1 else ""
    prs = list(bound)
    for number in _unique(loose):
        prs.append((repo, number))
    return {
        "repo": repo,
        "branch": _declared_branch(text),
        "prs": prs,
        "worktree": _declared_worktree(text),
    }


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def header_source_lines(text: str) -> list[str]:
    """The first non-empty line, then the first later line that starts with TASK."""
    lines = _nonempty_lines(text)
    if not lines:
        return []
    chosen = [lines[0]]
    for line in lines[1:]:
        if line.startswith("TASK"):
            chosen.append(line)
            break
    return chosen


def _issues_on_line(line: str) -> list[int]:
    """`issue #N` only. A bare `#N` or `PR #N` is not an issue."""
    return _unique(int(match) for match in _ISSUE_WORD.findall(line or ""))


def _numbers_on_line(line: str) -> list[int]:
    found: list[int] = []
    declaration = parse_prompt_declaration(line)
    for _repo, number in declaration.get("prs") or []:
        found.append(int(number))
    found.extend(_issues_on_line(line))
    found.extend(int(match) for match in _HASH_NUM.findall(line or ""))
    return _unique(found)


def _unique_on_line(line: str) -> dict | None:
    """One branch, else one PR, else one issue in one repo. Otherwise none.

    A branch wins even when the same line also names an issue or a PR
    (`after PR #655 merged`). Without a branch, the line must name exactly
    one number. `PR #370 and #371` is two numbers, not one PR.
    """
    declaration = parse_prompt_declaration(line)
    branches = _branch_names(line)
    prs: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for repo, number in declaration.get("prs") or []:
        key = (repo or "", int(number))
        if key not in seen:
            seen.add(key)
            prs.append(key)
    issues = _issues_on_line(line)
    repo = declaration.get("repo") or ""
    numbers = _numbers_on_line(line)
    if len(branches) == 1:
        return {
            "kind": "branch",
            "branch": branches[0],
            "repo": repo,
            "pr": 0,
            "issue": 0,
            "line": line,
        }
    if len(branches) > 1:
        return None
    if len(numbers) != 1:
        return None
    if len(prs) == 1:
        pr_repo, number = prs[0]
        return {
            "kind": "pr",
            "branch": "",
            "repo": pr_repo or repo,
            "pr": number,
            "issue": 0,
            "line": line,
        }
    if len(issues) == 1 and repo in REPOS:
        return {
            "kind": "issue",
            "branch": "",
            "repo": repo,
            "pr": 0,
            "issue": issues[0],
            "line": line,
        }
    return None


def header_target(text: str) -> dict:
    """Header declaration. `kind` is empty when the header does not decide.

    The first non-empty line wins when it names exactly one target.
    Otherwise the first line that starts with `TASK` is tried.
    `numbers` lists every number on those lines, for a coverage tie.
    """
    lines = header_source_lines(text)
    numbers: list[int] = []
    for line in lines:
        for number in _numbers_on_line(line):
            if number not in numbers:
                numbers.append(number)
    chosen: dict | None = None
    chosen_line = lines[0] if lines else ""
    for line in lines:
        target = _unique_on_line(line)
        if target is not None:
            chosen = target
            chosen_line = line
            break
    base = {
        "line": chosen_line,
        "kind": "",
        "branch": "",
        "repo": "",
        "pr": 0,
        "issue": 0,
        "numbers": numbers,
    }
    if chosen:
        base.update(chosen)
        base["numbers"] = numbers
    return base


class _PromptWindow:
    """User text before the first assistant turn or tool result.

    The rules preamble and the dispatch can be separate user records.
    `<user_query>` blocks are the declaration. Later tool output is not.
    """

    def __init__(self) -> None:
        self.user_parts: list[str] = []
        self.system_parts: list[str] = []
        self.saw_user = False
        self.closed = False

    def add_system(self, text: str) -> None:
        if self.closed or self.saw_user:
            return
        if text:
            self.system_parts.append(text)

    def add_user(self, text: str) -> None:
        if self.closed:
            return
        self.saw_user = True
        if text:
            self.user_parts.append(text)

    def close(self) -> None:
        self.closed = True

    def text(self) -> str:
        raw = "\n".join(self.user_parts) if self.saw_user else "\n".join(self.system_parts)
        blocks = _USER_QUERY.findall(raw)
        if blocks:
            return "\n".join(blocks)
        return raw


def _content_has_tool_result(content) -> bool:
    if not isinstance(content, list):
        return False
    return any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


def _feed_prompt(obj: dict, window: _PromptWindow) -> None:
    if window.closed:
        return
    if obj.get("synthetic_reason"):
        return
    if obj.get("type") == "response_item":
        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            return
        ptype = payload.get("type")
        if ptype == "message":
            role = payload.get("role")
            text = _parts_text(payload.get("content"))
            if role == "user":
                window.add_user(text)
            elif role in ("system", "developer"):
                window.add_system(text)
            elif role == "assistant":
                window.close()
            return
        if ptype in _CALL_TYPES or ptype in _OUTPUT_TYPES:
            window.close()
        return
    kind = obj.get("type")
    if kind in ("system", "developer"):
        window.add_system(_parts_text(obj.get("content")))
        return
    if kind == "assistant" or kind == "item.completed":
        window.close()
        return
    if kind == "tool_result":
        window.close()
        return
    message = obj.get("message") if isinstance(obj.get("message"), dict) else None
    if kind == "user" and message is not None:
        content = message.get("content")
        if _content_has_tool_result(content):
            window.close()
            return
        window.add_user(_parts_text(content))
        return
    if kind == "user":
        window.add_user(_parts_text(obj.get("content")))


def prompt_join_keys(
    declaration: dict,
    catalog: "PrCatalog",
    fallback_repo: str = "",
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Catalog keys for a declared branch and for declared PR numbers.

    A PR number written as `The-AIE/<repo>#N` stays on that repo. A bare
    `PR #N` uses the repo named in the prompt, then the session repo.
    """
    repo = declaration.get("repo") or ""
    if repo not in REPOS:
        repo = fallback_repo if fallback_repo in REPOS else ""
    branch = declaration.get("branch") or ""
    branch_keys = catalog.branch_keys(repo, branch) if branch else []
    pr_keys: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for item in declaration.get("prs") or []:
        repo_name, number = item
        if repo_name in REPOS:
            names = (repo_name,)
        elif repo:
            names = (repo,)
        else:
            names = REPOS
        for name in names:
            key = (name, int(number))
            if key in seen or key not in catalog.by_key:
                continue
            seen.add(key)
            pr_keys.append(key)
    return branch_keys, pr_keys


def _header_repo(header: dict, fallback_repo: str) -> str:
    repo = header.get("repo") or ""
    if repo in REPOS:
        return repo
    if fallback_repo in REPOS:
        return fallback_repo
    return ""


def _pr_keys_on_line(line: str, repo: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for pr_repo, number in parse_prompt_declaration(line).get("prs") or []:
        name = pr_repo if pr_repo in REPOS else repo
        key = (name, int(number))
        if not name or key in seen:
            continue
        seen.add(key)
        found.append(key)
    return found


def _catalog_pr_keys(
    pairs: list[tuple[str, int]],
    catalog: "PrCatalog",
    fallback_repo: str,
) -> list[tuple[str, int]]:
    _branch_keys, pr_keys = prompt_join_keys(
        {"repo": "", "branch": "", "prs": pairs},
        catalog,
        fallback_repo,
    )
    return pr_keys


def header_join_keys(
    header: dict,
    catalog: "PrCatalog",
    fallback_repo: str = "",
) -> list[tuple[str, int]]:
    """Catalog keys for a header that named a target.

    A branch on the header wins when the catalog has that branch.
    A branch the catalog does not have falls through to a PR or an issue
    on the same header line, not to numbers later in the prompt.
    Empty when nothing on the header is in the catalog. The caller still
    treats `kind` as a declaration, so the body is not searched either.
    """
    if not header or not header.get("kind"):
        return []
    repo = _header_repo(header, fallback_repo)
    kind = header.get("kind")
    if kind == "branch":
        keys = catalog.branch_keys(repo, header.get("branch") or "")
        if keys:
            return keys
        line = header.get("line") or ""
        pr_pairs = _pr_keys_on_line(line, repo)
        if pr_pairs:
            return _catalog_pr_keys(pr_pairs, catalog, fallback_repo)
        issues = _issues_on_line(line)
        if len(issues) == 1 and repo in REPOS:
            return catalog.issue_keys(repo, issues)
        return []
    if kind == "pr":
        number = int(header.get("pr") or 0)
        if number <= 0:
            return []
        return _catalog_pr_keys([(header.get("repo") or repo, number)], catalog, fallback_repo)
    if kind == "issue":
        issue = int(header.get("issue") or 0)
        if issue <= 0 or repo not in REPOS:
            return []
        return catalog.issue_keys(repo, [issue])
    return []


def relativize_repo_path(path: str, roots: list[str]) -> str:
    """Repo-relative path. Absolute paths outside the worktree are dropped."""
    text = (path or "").replace("\\", "/").strip().strip("`")
    if not text or text.startswith("<"):
        return ""
    if text.startswith("file://"):
        text = text[7:]
    cleaned: list[str] = []
    for root in roots:
        root_text = (root or "").replace("\\", "/").rstrip("/")
        if root_text:
            cleaned.append(root_text)
    cleaned.sort(key=len, reverse=True)
    if text.startswith("/"):
        matched = False
        for root in cleaned:
            if text == root:
                return ""
            prefix = root + "/"
            if text.startswith(prefix):
                text = text[len(prefix):]
                matched = True
                break
        if not matched:
            return ""
    text = text.lstrip("./")
    parts = [part for part in text.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return ""
    return "/".join(parts)


def paths_from_tool_arguments(arguments: str) -> list[str]:
    """File paths named by an edit or write call."""
    found: list[str] = []
    for match in _PATCH_PATH.finditer(arguments or ""):
        path = match.group(1) or match.group(2) or ""
        if path:
            found.append(path)
    try:
        obj = json.loads(arguments or "")
    except json.JSONDecodeError:
        obj = None

    def walk(node) -> None:
        if isinstance(node, dict):
            for key in _PATH_KEYS:
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if obj is not None:
        walk(obj)
    return found


def successful_edit_files(messages: list[dict], roots: list[str]) -> list[str]:
    """Repo-relative files whose edit tool result shows the file changed.

    Uses the same success rule as session role: call_writes_repo and
    edit_result_succeeded. A bare call is not an edit.
    """
    from training.historical.extract import (
        _tool_result_text,
        call_writes_repo,
        edit_result_succeeded,
    )

    found: list[str] = []
    seen: set[str] = set()
    for message in messages:
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            args = str(fn.get("arguments") or "")
            if not call_writes_repo(name, args):
                continue
            if not edit_result_succeeded(_tool_result_text(messages, str(call.get("id") or ""))):
                continue
            for path in paths_from_tool_arguments(args):
                relative = relativize_repo_path(path, roots)
                if relative and relative not in seen:
                    seen.add(relative)
                    found.append(relative)
    return found


def jaccard(left: set[str], right: set[str]) -> float:
    """Jaccard overlap. Two empty sets score 0."""
    if not left and not right:
        return 0.0
    union = len(left | right)
    if union == 0:
        return 0.0
    return len(left & right) / union


def edit_coverage(session: set[str], pr_files: set[str]) -> float:
    """Share of the session's edits that the pull request also changes.

    An empty session scores 0. Candidate picking and builder confirm both
    use this ratio. Jaccard against a merged pull request rejects a true
    subset, because the pull request is the union of every session plus
    the coordinator commit. Jaccard is not used to choose a pull request.
    """
    if not session:
        return 0.0
    return len(session & pr_files) / len(session)


def pick_by_coverage(
    scored: list[tuple[tuple[str, int], float]],
    header_numbers: set[int] | None = None,
) -> tuple[str, int] | None:
    """Highest coverage at or above 0.5 and at least 0.2 above the next.

    Equal coverage prefers the one tied candidate whose number is on the
    header line. Anything else stays ambiguous. Jaccard is not consulted.
    """
    if len(scored) < 2:
        return None
    ordered = sorted(scored, key=lambda item: (-item[1], item[0][0], item[0][1]))
    best = ordered[0][1]
    if best + 1e-9 < COVERAGE_PICK:
        return None
    leaders = [key for key, score in ordered if abs(score - best) <= 1e-9]
    if len(leaders) > 1:
        numbers = header_numbers or set()
        named = [key for key in leaders if key[1] in numbers]
        if len(named) == 1:
            return named[0]
        return None
    second = ordered[1][1]
    if best + 1e-9 >= second + COVERAGE_MARGIN:
        return ordered[0][0]
    return None


def resolve_overlap(
    decision: dict,
    session_files,
    pr_files_for,
    *,
    role: str,
    header_numbers: set[int] | None = None,
) -> dict:
    """Pick among ambiguous prompt or issue candidates, then confirm builders.

    pr_files_for(key) returns the pull request's path set, or None when the
    file list is unknown. Unknown lists do not reject a join and do not vote.
    The pick uses edit coverage. Role is not changed here: a reviewer stays
    a reviewer whether or not a pull request is chosen.
    """
    files = set(session_files or [])
    reason = decision.get("reason") or ""
    method = decision.get("join_method") or ""
    candidates = list(decision.get("candidates") or [])
    if reason in ("ambiguous_prompt", "ambiguous_issue") and len(candidates) >= 2 and files:
        scored: list[tuple[tuple[str, int], float]] = []
        for key in candidates:
            pr_files = pr_files_for(key)
            if pr_files is None:
                continue
            scored.append((key, edit_coverage(files, set(pr_files))))
        if len(scored) >= 2:
            picked = pick_by_coverage(scored, header_numbers)
            if picked is not None:
                return {
                    "join_method": JOIN_COVERAGE,
                    "reason": "",
                    "repo": picked[0],
                    "pr": picked[1],
                    "candidates": [],
                }
        return decision
    if method in _CONFIRM_METHODS and role == "builder":
        if not files:
            return {"join_method": "", "reason": "no_file_overlap", "repo": "", "pr": "", "candidates": []}
        key = (decision.get("repo") or "", int(decision.get("pr")))
        pr_files = pr_files_for(key)
        if pr_files is None:
            return decision
        if edit_coverage(files, set(pr_files)) + 1e-9 < OVERLAP_CONFIRM:
            return {"join_method": "", "reason": "no_file_overlap", "repo": "", "pr": "", "candidates": []}
    return decision


def _strip_quoted_command(command: str) -> str:
    command = re.sub(r'"(?:\\.|[^"\\])*"', '""', command)
    command = re.sub(r"'(?:\\.|[^'\\])*'", "''", command)
    return command


def _command_segments(command: str) -> list[str]:
    parts = re.split(r"&&|\|\||[;&|\n]", _strip_quoted_command(command or ""))
    return [part.strip() for part in parts if part.strip()]


def _git_segments(command: str) -> list[str]:
    return [part for part in _command_segments(command) if re.search(r"(?i)\bgit\b", part)]


def _is_commit_command(command: str) -> bool:
    if any(_GIT_COMMIT_SEG.search(segment) for segment in _git_segments(command)):
        return True
    from training.historical.extract import invokes_git_commit
    return invokes_git_commit(command or "")


def _head_sha_allowed(command: str, saw_commit: bool) -> bool:
    """True when this command's git invocations are only `rev-parse HEAD` after a commit."""
    segments = _git_segments(command)
    if not segments:
        return False
    commit_at = None
    head_at = None
    for index, segment in enumerate(segments):
        if _GIT_COMMIT_SEG.search(segment):
            commit_at = index
        elif _REV_PARSE_HEAD_SEG.search(segment):
            head_at = index
        else:
            return False
    if head_at is None:
        return False
    if commit_at is not None and head_at > commit_at:
        return True
    return saw_commit and all(_REV_PARSE_HEAD_SEG.search(segment) for segment in segments)


def commit_shas_from_tool_output(text: str) -> list[str]:
    """Bracket SHAs only. A bare line is not a commit the session created."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _COMMIT_BRACKET.finditer(text or ""):
        sha = match.group("sha")
        if sha not in seen:
            seen.add(sha)
            found.append(sha)
    return found


def commit_shas_from_events(events: list[tuple[str, str]]) -> list[str]:
    """SHAs from `git commit` output, or `git rev-parse HEAD` after such a commit."""
    found: list[str] = []
    seen: set[str] = set()
    saw_commit = False

    def add(sha: str) -> None:
        if sha and sha not in seen:
            seen.add(sha)
            found.append(sha)

    for command, output in events:
        command = command or ""
        output = output or ""
        if _is_commit_command(command):
            for match in _COMMIT_BRACKET.finditer(output):
                add(match.group("sha"))
                saw_commit = True
        if _head_sha_allowed(command, saw_commit):
            for match in _BARE_SHA.finditer(output):
                add(match.group(1))
    return found


def _displayed_shas(events: list[tuple[str, str]], created: set[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for command, output in events:
        if _is_commit_command(command or ""):
            continue
        for match in _SHA_TOKEN.finditer(output or ""):
            sha = match.group(1)
            if sha in created or sha in seen:
                continue
            seen.add(sha)
            found.append(sha)
    return found


def _sha_matches_candidate(sha: str, candidate_shas: set[str]) -> bool:
    needle = sha.lower()
    if len(needle) < 7:
        return False
    for candidate in candidate_shas:
        full = candidate.lower()
        if full == needle or (len(needle) >= 7 and full.startswith(needle)):
            return True
    return False


def usable_commit_shas(events: list[tuple[str, str]], candidate_shas: set[str] | None = None) -> list[str]:
    """Session-created SHAs, plus a displayed SHA that is a candidate head or commit."""
    created = commit_shas_from_events(events)
    if not candidate_shas:
        return created
    out = list(created)
    seen = set(out)
    for sha in _displayed_shas(events, seen):
        if sha in seen:
            continue
        if _sha_matches_candidate(sha, candidate_shas):
            seen.add(sha)
            out.append(sha)
    return out


def candidate_commit_shas(catalog: "PrCatalog", repo: str, issues: list[int]) -> set[str]:
    """Head and commit SHAs on pull requests that close these issues, when the catalog has them."""
    found: set[str] = set()
    if catalog is None or not issues:
        return found
    for key in catalog.issue_keys(repo, issues):
        pr = catalog.by_key.get(key) or {}
        for value in (pr.get("headOid"), pr.get("headSha")):
            if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", value):
                found.add(value.lower())
        for commit in pr.get("commits") or []:
            sha = commit.get("oid") if isinstance(commit, dict) else commit
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
                found.add(sha.lower())
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


def _command_text(raw) -> str:
    """The shell command inside a tool call. Empty when the call is not a command."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        for key in ("command", "cmd"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value
        action = raw.get("action")
        if isinstance(action, dict):
            cmd = action.get("command")
            if isinstance(cmd, list):
                return " ".join(str(part) for part in cmd)
            if isinstance(cmd, str) and cmd.strip():
                return cmd
        for key in ("arguments", "input"):
            if key in raw:
                found = _command_text(raw.get(key))
                if found:
                    return found
        return ""
    if isinstance(raw, list):
        return " ".join(str(part) for part in raw)
    text = str(raw).strip()
    if not text:
        return ""
    if text[0] in "{[":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, (dict, list)):
            found = _command_text(parsed)
            if found:
                return found
        from training.historical.extract import extract_shell_commands
        found_cmds = extract_shell_commands(text)
        return "\n".join(found_cmds) if found_cmds else ""
    from training.historical.extract import extract_shell_commands
    found_cmds = extract_shell_commands(text)
    if found_cmds:
        return "\n".join(found_cmds)
    return text


def _looks_like_git(command: str) -> bool:
    return bool(re.search(r"(?i)\bgit\b", command or ""))


class _SignalBag:
    """Git commands in file order, paired with the tool result that belongs to them."""

    def __init__(self) -> None:
        self.user_parts: list[str] = []
        self.events: list[list[str]] = []
        self.index_by_id: dict[str, int] = {}
        self.pending_out: dict[str, list[str]] = {}

    def add_user(self, text: str) -> None:
        if text:
            self.user_parts.append(text)

    def add_call(self, call_id: str, command: str) -> None:
        command = command or ""
        if not _looks_like_git(command):
            return
        if call_id and call_id in self.index_by_id:
            idx = self.index_by_id[call_id]
            prev = self.events[idx][0]
            self.events[idx][0] = f"{prev}\n{command}".strip() if prev else command
            return
        self.events.append([command, ""])
        idx = len(self.events) - 1
        if not call_id:
            return
        self.index_by_id[call_id] = idx
        for output in self.pending_out.pop(call_id, []):
            self._append_out(idx, output)

    def add_output(self, call_id: str, output: str) -> None:
        output = output or ""
        if not call_id:
            return
        idx = self.index_by_id.get(call_id)
        if idx is None:
            self.pending_out.setdefault(call_id, []).append(output)
            return
        self._append_out(idx, output)

    def add_paired(self, command: str, output: str) -> None:
        if not _looks_like_git(command):
            return
        self.events.append([command or "", output or ""])

    def _append_out(self, idx: int, output: str) -> None:
        prev = self.events[idx][1]
        self.events[idx][1] = f"{prev}\n{output}" if prev else output

    def finished(self) -> list[tuple[str, str]]:
        seen: set[tuple[str, str]] = set()
        out: list[tuple[str, str]] = []
        for command, output in self.events:
            key = (command, output)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out


def _consume(obj: dict, vendor: str, bag: _SignalBag) -> None:
    """Pull user text and git command/output pairs out of one session record."""
    del vendor
    if obj.get("type") == "response_item":
        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            return
        ptype = payload.get("type")
        if ptype == "message" and payload.get("role") == "user":
            bag.add_user(_parts_text(payload.get("content")))
        elif ptype in _CALL_TYPES:
            bag.add_call(
                str(payload.get("call_id") or payload.get("id") or ""),
                _command_text(payload),
            )
        elif ptype in _OUTPUT_TYPES:
            out = payload.get("output")
            if out is None:
                out = payload.get("aggregated_output")
            bag.add_output(str(payload.get("call_id") or payload.get("id") or ""), _parts_text(out))
        return
    if obj.get("type") == "item.completed":
        item = obj.get("item") or {}
        if isinstance(item, dict) and item.get("type") == "command_execution":
            bag.add_paired(str(item.get("command") or ""), _parts_text(item.get("aggregated_output")))
        return
    kind = obj.get("type")
    message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    content = message.get("content") if message else None
    if kind == "assistant" and isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                bag.add_call(str(block.get("id") or ""), _command_text(block.get("input")))
        return
    if kind == "assistant" and obj.get("tool_calls"):
        for call in obj.get("tool_calls") or []:
            if isinstance(call, dict):
                bag.add_call(str(call.get("id") or ""), _command_text(call.get("arguments")))
        return
    if kind == "user" and message:
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    bag.add_output(
                        str(block.get("tool_use_id") or block.get("tool_call_id") or ""),
                        _parts_text(block.get("content")),
                    )
                elif block.get("type") == "text":
                    bag.add_user(str(block.get("text") or ""))
        elif isinstance(content, str):
            bag.add_user(content)
        return
    if kind == "user":
        bag.add_user(_parts_text(obj.get("content")))
        return
    if kind == "tool_result":
        bag.add_output(
            str(obj.get("tool_call_id") or obj.get("tool_use_id") or ""),
            _parts_text(obj.get("content")),
        )


def _session_edit_facts(path: Path, vendor: str, roots: list[str]) -> tuple[list[str], str]:
    """Successfully edited paths and the session role. Empty when the file will not parse."""
    from training.historical.extract import ParseSkip, classify_session_role, parse_session, session_sandbox

    if not path.exists():
        return [], ""
    try:
        messages = parse_session(path, vendor)
        sandbox = session_sandbox(path)
    except (OSError, ParseSkip, json.JSONDecodeError):
        return [], ""
    return successful_edit_files(messages, roots), classify_session_role(messages, sandbox)


def collect_signals(
    path: Path,
    vendor: str,
    cwd: str,
    catalog: "PrCatalog | None" = None,
    repo: str = "",
) -> dict:
    """Read a session once. Returns created SHAs, issue numbers, and a prompt repo."""
    bag = _SignalBag()
    window = _PromptWindow()
    files: list[Path]
    if path.is_dir():
        chat = path / "chat_history.jsonl"
        files = [chat] if chat.is_file() else []
    else:
        files = [path] if path.is_file() else []
    for fp in files:
        try:
            rows = _iter_jsonl(fp)
        except OSError:
            continue
        for obj in rows:
            _feed_prompt(obj, window)
            _consume(obj, vendor, bag)
    user_text = "\n".join(bag.user_parts)
    issues = issues_for_join(cwd, user_text)
    prompt = window.text()
    declaration = parse_prompt_declaration(prompt)
    header = header_target(prompt)
    candidates: set[str] = set()
    if catalog is not None and issues:
        candidates = candidate_commit_shas(catalog, repo or repo_hint(cwd, user_text), issues)
    shas = usable_commit_shas(bag.finished(), candidates)
    edited: list[str] = []
    role = ""
    if declaration.get("branch") or declaration.get("prs") or issues or header.get("kind"):
        roots = [cwd or "", declaration.get("worktree") or header.get("worktree") or ""]
        edited, role = _session_edit_facts(path, vendor, roots)
    return {
        "shas": shas,
        "issues": issues,
        "prompt_repo": repo_from_prompt(user_text) or declaration.get("repo") or header.get("repo") or "",
        "sha_overflow": len(shas) > MAX_COMMIT_SHAS,
        "declaration": declaration,
        "header": header,
        "files": edited,
        "role": role,
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
    prompt_branch_keys: list[tuple[str, int]] | None = None,
    prompt_pr_keys: list[tuple[str, int]] | None = None,
    prompt_branch_attempted: bool = False,
    prompt_pr_attempted: bool = False,
    header_keys: list[tuple[str, int]] | None = None,
    header_declared: bool = False,
) -> dict:
    """Pick the winning method. Keys are (repo, pr_number)."""

    def one(keys: list[tuple[str, int]]) -> tuple[str, int] | None:
        uniq = _unique_keys(keys)
        if len(uniq) == 1:
            return uniq[0]
        return None

    def finish(method: str, picked: tuple[str, int]) -> dict:
        return {
            "join_method": method,
            "reason": "",
            "repo": picked[0],
            "pr": picked[1],
            "candidates": [],
        }

    def ambiguous(reason: str, keys: list[tuple[str, int]]) -> dict:
        return {
            "join_method": "",
            "reason": reason,
            "repo": "",
            "pr": "",
            "candidates": _unique_keys(keys),
        }

    if branch_keys:
        picked = one(branch_keys)
        if picked is not None:
            return finish(JOIN_BRANCH, picked)
        return ambiguous("ambiguous_branch", branch_keys)
    if header_declared:
        uniq = _unique_keys(header_keys or [])
        if len(uniq) > 1:
            return ambiguous("ambiguous_prompt", uniq)
        if len(uniq) == 1:
            return finish(JOIN_PROMPT_HEADER, uniq[0])
    elif prompt_branch_attempted:
        uniq = _unique_keys(prompt_branch_keys or [])
        if len(uniq) > 1:
            return ambiguous("ambiguous_prompt", uniq)
        if len(uniq) == 1:
            return finish(JOIN_PROMPT_BRANCH, uniq[0])
    elif prompt_pr_attempted:
        uniq = _unique_keys(prompt_pr_keys or [])
        if len(uniq) > 1:
            return ambiguous("ambiguous_prompt", uniq)
        if len(uniq) == 1:
            return finish(JOIN_PROMPT_PR, uniq[0])
    if commit_attempted:
        if len(_unique_keys(commit_keys)) > 1:
            picked = _merged_unique(commit_keys, pr_states)
            if picked is not None:
                return finish(JOIN_COMMIT_MERGED, picked)
            return ambiguous("ambiguous_commit", commit_keys)
        picked = one(commit_keys)
        if picked is not None:
            return finish(JOIN_COMMIT, picked)
    if issue_attempted:
        if len(_unique_keys(issue_keys)) > 1:
            picked = _merged_unique(issue_keys, pr_states)
            if picked is not None:
                return finish(JOIN_ISSUE_MERGED, picked)
            return ambiguous("ambiguous_issue", issue_keys)
        picked = one(issue_keys)
        if picked is not None:
            return finish(JOIN_ISSUE, picked)
    prompt_attempted = header_declared or prompt_branch_attempted or prompt_pr_attempted
    if not commit_attempted and not issue_attempted and not branch_keys and not prompt_attempted:
        return {"join_method": "", "reason": "no_signal", "repo": "", "pr": "", "candidates": []}
    return {"join_method": "", "reason": "no_match", "repo": "", "pr": "", "candidates": []}
