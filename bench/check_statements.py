#!/usr/bin/env python3
"""Fail when a task statement leaks a commit, the fixing pull request, a
fail-to-pass id, or a line copied from gold.patch.

File names that the original issue used are allowed. The checker looks at
problem_statement and issue_title.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
TASKS = BENCH / "tasks"

# A commit sha is 7-40 hex characters and contains a letter, so a decimal
# run id is not a sha. A hyphen on either side keeps UUID fragments out.
SHA_RE = re.compile(
    r"(?<![0-9a-fA-F-])(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{7,40}(?![0-9a-fA-F-])"
)


def _fixing_pr_patterns(pr: int) -> list[re.Pattern[str]]:
    number = str(int(pr))
    return [
        re.compile(rf"(?<![\w/])#{number}(?!\d)"),
        re.compile(rf"(?i)(?<![\w/])(?:pull request|pull|pr)\s*#?\s*{number}(?!\d)"),
        re.compile(rf"github\.com/\S+/(?:pull|commit)/{number}(?!\d)"),
    ]


def _name_present(text: str, name: str) -> bool:
    if not name:
        return False
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None


def gold_content_lines(gold: str) -> set[str]:
    lines: set[str] = set()
    for raw in gold.splitlines():
        if raw.startswith((
            "diff --git", "index ", "--- ", "+++ ", "@@", "new file",
            "deleted file", "similarity ", "rename ", "old mode", "new mode",
            "Binary files", "\\",
        )):
            continue
        if not raw or raw[0] not in "+- ":
            continue
        content = raw[1:].rstrip()
        if len(content) >= 40:
            lines.add(content)
    return lines


def statement_problems(text: str, *, pr: int, f2p_ids: list[str], gold: str) -> list[dict]:
    problems: list[dict] = []
    for match in SHA_RE.finditer(text or ""):
        problems.append({"kind": "sha", "detail": match.group(0)})
    for pattern in _fixing_pr_patterns(pr):
        found = pattern.search(text or "")
        if found:
            problems.append({"kind": "fixing_pr", "detail": found.group(0)})
            break
    for test_id in f2p_ids:
        if test_id and test_id in (text or ""):
            problems.append({"kind": "f2p", "detail": test_id})
            continue
        name = test_id.split("::")[-1] if test_id else ""
        if _name_present(text or "", name):
            problems.append({"kind": "f2p", "detail": name})
    copied = gold_content_lines(gold)
    for line in (text or "").splitlines():
        stripped = line.rstrip()
        if len(stripped) >= 40 and stripped in copied:
            problems.append({"kind": "gold_line", "detail": stripped[:120]})
    return problems


def scan_tasks(tasks_dir: Path = TASKS) -> list[dict]:
    failures = []
    for path in sorted(tasks_dir.glob("*/task.json")):
        task = json.loads(path.read_text())
        gold_path = path.parent / "gold.patch"
        gold = gold_path.read_text(errors="replace") if gold_path.is_file() else ""
        f2p_ids = list((task.get("f2p") or {}).get("test_ids") or [])
        pr = int(task["pr"])
        for field in ("problem_statement", "issue_title"):
            text = task.get(field) or ""
            if not isinstance(text, str):
                continue
            problems = statement_problems(text, pr=pr, f2p_ids=f2p_ids, gold=gold)
            if problems:
                failures.append({
                    "task_id": task.get("task_id") or path.parent.name,
                    "field": field,
                    "problems": problems,
                })
    return failures


def main(argv: list[str] | None = None) -> int:
    del argv
    failures = scan_tasks()
    if failures:
        for item in failures:
            kinds = ", ".join(sorted({problem["kind"] for problem in item["problems"]}))
            print(f"{item['task_id']} {item['field']}: {kinds}")
            for problem in item["problems"][:8]:
                print(f"  {problem['kind']}: {problem['detail']}")
        print(f"statements: {len(failures)} field(s) failed")
        return 1
    count = len(list(TASKS.glob("*/task.json")))
    print(f"ok tasks={count}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
