#!/usr/bin/env python3
"""Reset fixtures/ from fixture_templates/ and assert fix-tasks FAIL verification.

Investigation tasks are expected to have verify_cmd == true (no auto fail).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OBS = Path(__file__).resolve().parents[1]
REPO_ROOT = OBS.parents[2]


def main() -> int:
    manifest = json.loads((OBS / "tasks.manifest.json").read_text())
    templates = OBS / "fixture_templates"
    fixtures = OBS / "fixtures"
    if not templates.exists():
        print(f"missing {templates}", file=sys.stderr)
        return 2
    if fixtures.exists():
        shutil.rmtree(fixtures)
    shutil.copytree(templates, fixtures)

    bad = []
    for t in manifest["tasks"]:
        if t.get("kind") == "investigate" or (t.get("verify_cmd") or "") == "true":
            continue
        cmd = t.get("verify_cmd") or "python3 -m unittest -q"
        src = fixtures / t["task_id"]
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "f"
            shutil.copytree(src, dst)
            r = subprocess.run(cmd, shell=True, cwd=str(dst), capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                bad.append(t["task_id"])
    if bad:
        print("ERROR: these fix fixtures already pass (not pristine):", bad)
        return 1
    print(f"OK reset fixtures from templates; {len(manifest['tasks'])} tasks; pristine for fix kinds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
