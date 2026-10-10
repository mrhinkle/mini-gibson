#!/usr/bin/env python3
"""Parallel wrapper around observational_runner.py (ThreadPoolExecutor).

Same env vars as observational_runner.py, plus:
  OBS_WORKERS   default 3
  OBS_TARGET_ROWS / OBS_SPEND_CAP_USD honored via STOP file + shared append lock
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "observational_runner", str(HERE / "observational_runner.py")
)
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)

WORKERS = int(os.environ.get("OBS_WORKERS", "3"))
TARGET = int(os.environ.get("OBS_TARGET_ROWS", str(v1.TARGET_ROWS)))
CAP = float(os.environ.get("OBS_SPEND_CAP_USD", str(v1.SPEND_CAP)))
STOP_FILE = v1.STOP_FILE
append_lock = threading.Lock()
task_locks: dict[str, threading.Lock] = {}
stop_evt = threading.Event()

_orig_append = v1.append_row


def locked_append(row):
    with append_lock:
        ids = {r["run_id"] for r in v1.existing_rows()}
        if row["run_id"] in ids:
            print(f"  dedupe {row['run_id']}", flush=True)
            return
        if len(ids) >= TARGET:
            stop_evt.set()
            return
        _orig_append(row)


v1.append_row = locked_append


def job(task, attempt, tmpl_root, seen):
    if stop_evt.is_set() or STOP_FILE.exists():
        stop_evt.set()
        return
    lock = task_locks.setdefault(task["task_id"], threading.Lock())
    with lock:
        if stop_evt.is_set():
            return
        rows = v1.existing_rows()
        if len(rows) >= TARGET:
            stop_evt.set()
            return
        if sum(1 for r in rows if r["task_id"] == task["task_id"]) >= attempt:
            return
        try:
            spent, _ = v1.spend_so_far()
        except Exception as e:
            print(f"  spend check err {e}", flush=True)
            spent = 0
        if spent >= CAP * 0.98:
            print(f"STOP spend ${spent:.4f}", flush=True)
            stop_evt.set()
            return
        print(f"run {task['task_id']} a{attempt}", flush=True)
        try:
            v1.run_one(task, attempt, tmpl_root, seen)
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT {task['task_id']} a{attempt}", flush=True)
        except Exception as e:
            print(
                f"  ERROR {task['task_id']} a{attempt} {type(e).__name__}: {e}",
                flush=True,
            )


def main():
    tasks = json.loads(v1.MANIFEST.read_text())["tasks"]
    tmpl_root = v1.ensure_templates(tasks)
    seen = v1.existing_run_ids(v1.existing_rows())
    print(
        f"parallel start rows={len(seen)} tasks={len(tasks)} workers={WORKERS} "
        f"target={TARGET} cap=${CAP}",
        flush=True,
    )
    work = [(t, a) for a in range(1, 6) for t in tasks]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(job, t, a, tmpl_root, seen) for t, a in work]
        for f in futs:
            f.result()
    try:
        spent, rem = v1.spend_so_far()
        print(
            f"DONE rows={len(v1.existing_rows())} spend=${spent:.4f} remaining=${rem:.4f}",
            flush=True,
        )
    except Exception:
        print(f"DONE rows={len(v1.existing_rows())}", flush=True)


if __name__ == "__main__":
    main()
