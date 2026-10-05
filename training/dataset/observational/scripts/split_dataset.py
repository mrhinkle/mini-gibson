#!/usr/bin/env python3
"""Split runs.jsonl into DEV / TEST by task_id (held-out tasks, not random rows).

Default: hold out ~20% of task_ids for TEST_OBSERVATIONAL.
Writes under OBS_ROOT/splits/ (gitignored).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

OBS_ROOT_DEFAULT = Path(__file__).resolve().parents[1]  # .../training/dataset/observational
REPO_ROOT = OBS_ROOT_DEFAULT.parents[2]
DEFAULT_OBS = OBS_ROOT_DEFAULT


def stable_bucket(task_id: str, salt: str) -> float:
    h = hashlib.sha256(f"{salt}:{task_id}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=DEFAULT_OBS / "runs.jsonl")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OBS / "splits")
    ap.add_argument("--test-fraction", type=float, default=0.2)
    ap.add_argument("--salt", default="mini-gibson-433-v1")
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.runs.read_text().splitlines() if l.strip()]
    by_task: dict[str, list] = defaultdict(list)
    for r in rows:
        by_task[r["task_id"]].append(r)

    test_tasks = sorted(
        tid for tid in by_task if stable_bucket(tid, args.salt) < args.test_fraction
    )
    dev_tasks = sorted(set(by_task) - set(test_tasks))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    dev_path = args.out_dir / "runs.dev.jsonl"
    test_path = args.out_dir / "runs.test.jsonl"
    meta = {
        "salt": args.salt,
        "test_fraction": args.test_fraction,
        "dev_tasks": dev_tasks,
        "test_tasks": test_tasks,
        "dev_rows": sum(len(by_task[t]) for t in dev_tasks),
        "test_rows": sum(len(by_task[t]) for t in test_tasks),
    }

    def write(path: Path, task_ids: list[str], split_name: str) -> None:
        with path.open("w") as f:
            for tid in task_ids:
                for r in by_task[tid]:
                    out = dict(r)
                    out["split"] = split_name
                    f.write(json.dumps(out, ensure_ascii=False) + "\n")

    write(dev_path, dev_tasks, "DEV_OBSERVATIONAL")
    write(test_path, test_tasks, "TEST_OBSERVATIONAL")
    (args.out_dir / "split_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
