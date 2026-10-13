"""Verifier gates for frozen Gibson Bench tasks.

The integration cases need a local checkout. Conference-os and chatterbuilt
also need a vitest install. Paths are built from the home directory so this
file does not embed a host path or a login. The broken-setup case does not
need either.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "bench" / "verify.py"
TASKS = ("conference-os-2274", "conference-os-2244")
GOLD_EMPTY = (
    ("conference-os-2274", "conference-os"),
    ("conference-os-2244", "conference-os"),
    ("the-gibson-203", "the-gibson"),
    ("chatterbuilt-352", "chatterbuilt"),
)

MIRROR = Path.home() / "Code" / "conference-os"
MODULES = Path.home() / "Code" / "conference-os-wt" / "ata-parent-nav-ctas" / "node_modules"
GIBSON = Path.home() / "Code" / "the-gibson"
CHATTER = Path.home() / "Code" / "chatterbuilt"
CHATTER_MODULES = CHATTER / "apps" / "mcp" / "node_modules"
needs_checkout = pytest.mark.skipif(
    not (MIRROR.is_dir() and (MODULES / ".bin" / "vitest").is_file()),
    reason="local conference-os checkout or vitest install is absent",
)


def _ready(repo: str) -> bool:
    if repo == "conference-os":
        return MIRROR.is_dir() and (MODULES / ".bin" / "vitest").is_file()
    if repo == "the-gibson":
        return GIBSON.is_dir()
    if repo == "chatterbuilt":
        return CHATTER.is_dir() and (CHATTER_MODULES / ".bin" / "vitest").is_file()
    return False


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env.pop("FORCE_COLOR", None)
    env["GIBSON_BENCH_MIRRORS"] = json.dumps({
        "conference-os": str(MIRROR),
        "the-gibson": str(GIBSON),
        "chatterbuilt": str(CHATTER),
    })
    modules = {"conference-os": str(MODULES)}
    if (CHATTER_MODULES / ".bin" / "vitest").is_file():
        modules["chatterbuilt"] = str(CHATTER_MODULES)
    env["GIBSON_BENCH_NODE_MODULES"] = json.dumps(modules)
    return env


def _run(task_id: str, patch: Path, env: dict[str, str]) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(VERIFY), task_id, str(patch)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"verifier stdout was not JSON: {proc.stdout[-500:]}\n{proc.stderr[-500:]}") from exc
    return proc.returncode, payload


def test_shell_suite_id_follows_exit_and_named_checks() -> None:
    from bench.verify import _shell_statuses

    text = "  ok   — alpha\n  FAIL — beta\n"
    failed = _shell_statuses(text, "bash scripts/tests/demo.test.sh", 1)
    assert failed["scripts/tests/demo.test.sh::alpha"] == "passed"
    assert failed["scripts/tests/demo.test.sh::beta"] == "failed"
    assert failed["scripts/tests/demo.test.sh::__suite__"] == "failed"

    clean = _shell_statuses("  ok   — alpha\n", "bash scripts/tests/demo.test.sh", 0)
    assert clean["scripts/tests/demo.test.sh::__suite__"] == "passed"


@pytest.mark.parametrize("task_id,repo", GOLD_EMPTY)
def test_gold_patch_resolves(task_id: str, repo: str) -> None:
    if not _ready(repo):
        pytest.skip(f"local {repo} checkout or vitest install is absent")
    code, payload = _run(task_id, ROOT / "bench" / "tasks" / task_id / "gold.patch", _env())
    assert payload.get("error") is None
    assert payload["f2p_pass"] is True
    assert payload["p2p_pass"] is True
    assert payload["resolved"] is True
    assert code == 0


@pytest.mark.parametrize("task_id,repo", GOLD_EMPTY)
def test_empty_patch_is_not_resolved(task_id: str, repo: str, tmp_path: Path) -> None:
    if not _ready(repo):
        pytest.skip(f"local {repo} checkout or vitest install is absent")
    empty = tmp_path / "empty.patch"
    empty.write_text("")
    code, payload = _run(task_id, empty, _env())
    assert "error" not in payload
    assert payload["resolved"] is False
    assert payload["f2p_pass"] is False
    assert code == 1


@needs_checkout
@pytest.mark.parametrize("task_id", TASKS)
def test_test_patch_only_is_not_resolved(task_id: str) -> None:
    code, payload = _run(task_id, ROOT / "bench" / "tasks" / task_id / "test.patch", _env())
    assert "error" not in payload
    assert payload["resolved"] is False
    assert payload["f2p_pass"] is False
    assert code == 1


def test_broken_mirror_is_an_error_and_not_resolved(tmp_path: Path) -> None:
    empty = tmp_path / "empty.patch"
    empty.write_text("")
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["GIBSON_BENCH_MIRRORS"] = json.dumps({
        "conference-os": "/no/such/conference-os-mirror",
    })
    env.pop("GIBSON_BENCH_NODE_MODULES", None)
    code, payload = _run("conference-os-2274", empty, env)
    assert payload["resolved"] is False
    assert payload["f2p_pass"] is False
    assert payload["p2p_pass"] is False
    assert payload.get("error")
    assert code == 1
