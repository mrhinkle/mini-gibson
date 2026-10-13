#!/usr/bin/env python3
"""Fail when a bench task overlaps the train-v7 builder set.

train-v7.keys.json is a sorted list of {repo, pr, issues[]} for every builder
pull request in ~/gibson-traces/sft/train-v7.jsonl. Issue numbers are the
episode's issue field plus that pull request's same-repo closing issues.
The file stores numbers only.

Exit 1 if any task's (repo, pr) is in that list, or if the task shares an
issue number with a train pull request in the same repository. The same
issue number in two repositories is two issues.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
KEYS_PATH = BENCH / "contamination" / "train-v7.keys.json"
TASKS = BENCH / "tasks"


def load_keys(path: Path = KEYS_PATH) -> list[dict]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise SystemExit("train-v7.keys.json must be a list")
    return data


def load_tasks(tasks_dir: Path = TASKS) -> list[dict]:
    found = []
    for path in sorted(tasks_dir.glob("*/task.json")):
        task = json.loads(path.read_text())
        issues = task.get("issues")
        if issues is None and isinstance(task.get("issue_number"), int):
            issues = [task["issue_number"]]
        if not isinstance(issues, list):
            issues = []
        found.append({
            "task_id": task.get("task_id") or path.parent.name,
            "repo": task.get("repo"),
            "pr": task.get("pr"),
            "issues": [item for item in issues if isinstance(item, int)],
        })
    return found


def find_overlaps(tasks: list[dict], keys: list[dict]) -> list[dict]:
    train_prs = {(item["repo"], item["pr"]) for item in keys}
    train_issues: dict[str, set[int]] = {}
    for item in keys:
        bucket = train_issues.setdefault(item["repo"], set())
        for number in item.get("issues") or []:
            if isinstance(number, int):
                bucket.add(number)
    overlaps = []
    for task in tasks:
        reasons = []
        if (task["repo"], task["pr"]) in train_prs:
            reasons.append("pull request is in train-v7")
        shared = sorted(
            number for number in task["issues"]
            if number in train_issues.get(task["repo"], ())
        )
        if shared:
            reasons.append("shares issue " + ", ".join(str(number) for number in shared))
        if reasons:
            overlaps.append({
                "task_id": task["task_id"],
                "repo": task["repo"],
                "pr": task["pr"],
                "reasons": reasons,
            })
    return overlaps


def main(argv: list[str] | None = None) -> int:
    del argv
    keys = load_keys()
    tasks = load_tasks()
    overlaps = find_overlaps(tasks, keys)
    if overlaps:
        for item in overlaps:
            print(f"{item['task_id']}: {'; '.join(item['reasons'])}")
        print(f"contamination: {len(overlaps)} task(s) overlap train-v7 ({len(keys)} pull requests)")
        return 1
    print(f"ok tasks={len(tasks)} train_prs={len(keys)} overlaps=0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
