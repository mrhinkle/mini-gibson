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


def test_nonzero_exit_is_not_resolved_when_every_id_passes() -> None:
    from bench.verify import score_sides

    statuses = {"tests/unit/demo.test.ts::alpha": "passed"}
    records = [{
        "sides": ["f2p", "p2p"],
        "returncode": 1,
        "timed_out": False,
        "missing_report": False,
        "statuses": statuses,
    }]
    scored = score_sides(
        statuses,
        ["tests/unit/demo.test.ts::alpha"],
        ["tests/unit/demo.test.ts::alpha"],
        records,
    )
    assert scored["f2p_pass"] is False
    assert scored["p2p_pass"] is False
    assert scored["resolved"] is False


def test_missing_report_is_not_resolved() -> None:
    from bench.verify import score_sides

    statuses = {"tests/unit/demo.test.ts::alpha": "passed"}
    records = [{
        "sides": ["f2p", "p2p"],
        "returncode": 0,
        "timed_out": False,
        "missing_report": True,
        "statuses": statuses,
    }]
    scored = score_sides(
        statuses,
        ["tests/unit/demo.test.ts::alpha"],
        ["tests/unit/demo.test.ts::alpha"],
        records,
    )
    assert scored["resolved"] is False
    assert scored["f2p_pass"] is False
    assert scored["p2p_pass"] is False


def test_failed_suite_status_blocks_a_clean_exit() -> None:
    from bench.verify import score_sides

    statuses = {
        "scripts/tests/demo.test.sh::alpha": "passed",
        "scripts/tests/demo.test.sh::__suite__": "failed",
    }
    records = [{
        "sides": ["f2p"],
        "returncode": 0,
        "timed_out": False,
        "missing_report": False,
        "statuses": statuses,
    }]
    scored = score_sides(statuses, ["scripts/tests/demo.test.sh::alpha"], [], records)
    assert scored["f2p_pass"] is False
    assert scored["resolved"] is False


def test_timeout_is_not_a_pass() -> None:
    from bench.verify import score_sides

    statuses = {"scripts/tests/demo.test.sh::alpha": "passed"}
    records = [{
        "sides": ["f2p"],
        "returncode": None,
        "timed_out": True,
        "missing_report": False,
        "statuses": statuses,
    }]
    scored = score_sides(statuses, ["scripts/tests/demo.test.sh::alpha"], [], records)
    assert scored["resolved"] is False


def test_test_globs_cover_hidden_tests_and_not_the_270_runner() -> None:
    from bench.verify import _matches_test_glob

    broad = ["**/*.test.*", "**/tests/**", "scripts/tests/**"]
    assert _matches_test_glob("tests/unit/security-headers.test.ts", broad)
    assert _matches_test_glob("apps/mcp/lib/prepare-agent-suggestion.test.ts", broad)
    assert _matches_test_glob("scripts/tests/wall-timeout.test.sh", broad)
    assert _matches_test_glob("scripts/tests/run-all.sh", broad)
    assert not _matches_test_glob("src/lib/security-headers.ts", broad)
    # the-gibson-270's product file is the runner. Its globs leave that file in place.
    narrow = ["**/*.test.*"]
    assert _matches_test_glob("scripts/tests/wall-timeout.test.sh", narrow)
    assert not _matches_test_glob("scripts/tests/run-all.sh", narrow)


def test_contamination_detector_flags_pr_and_same_repo_issue() -> None:
    from bench.check_contamination import find_overlaps

    keys = [{"repo": "conference-os", "pr": 9, "issues": [3, 4]}]
    tasks = [
        {"task_id": "t-pr", "repo": "conference-os", "pr": 9, "issues": [1]},
        {"task_id": "t-issue", "repo": "conference-os", "pr": 8, "issues": [4]},
        {"task_id": "t-other-repo", "repo": "the-gibson", "pr": 8, "issues": [4]},
    ]
    found = {item["task_id"] for item in find_overlaps(tasks, keys)}
    assert found == {"t-pr", "t-issue"}


def test_statement_detector_flags_sha_pr_id_and_copied_line() -> None:
    from bench.check_statements import statement_problems

    gold = (
        "diff --git a/src/a.ts b/src/a.ts\n"
        "--- a/src/a.ts\n"
        "+++ b/src/a.ts\n"
        "@@ -1 +1 @@\n"
        "+export const exactlyFortyCharactersOfSolutionCode = 1\n"
    )
    text = (
        "See commit abcd1234 and PR #15.\n"
        "export const exactlyFortyCharactersOfSolutionCode = 1\n"
        "tests/unit/a.test.ts::the assertion name\n"
    )
    kinds = {
        problem["kind"]
        for problem in statement_problems(
            text,
            pr=15,
            f2p_ids=["tests/unit/a.test.ts::the assertion name"],
            gold=gold,
        )
    }
    assert kinds == {"sha", "fixing_pr", "f2p", "gold_line"}


def test_contamination_and_statement_checks_pass() -> None:
    env = os.environ.copy()
    for script in ("check_contamination.py", "check_statements.py"):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "bench" / script)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert proc.stdout.startswith("ok ")


def _git_style_patch(rel: str, old: str, new: str, tmp_path: Path) -> str:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.write_text(old)
    right.write_text(new)
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--text", "--", str(left), str(right)],
        capture_output=True,
        text=True,
        check=False,
    )
    text = proc.stdout.replace(str(left).lstrip("/"), rel).replace(str(right).lstrip("/"), rel)
    if not text.endswith("\n"):
        text += "\n"
    return text


def test_tampered_assertion_is_reverted_and_not_resolved(tmp_path: Path) -> None:
    if not _ready("the-gibson"):
        pytest.skip("local the-gibson checkout is absent")
    task_id = "the-gibson-338"
    task = json.loads((ROOT / "bench" / "tasks" / task_id / "task.json").read_text())
    rel = "scripts/tests/silent-noop.test.sh"
    show = subprocess.run(
        ["git", "-C", str(GIBSON), "show", f"{task['base_sha']}:{rel}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert show.returncode == 0, show.stderr
    names = [
        test_id.split("::", 1)[1]
        for bucket in (task["f2p"], task["p2p"])
        for test_id in bucket["test_ids"]
    ]
    stub = "#!/bin/bash\n" + "".join(f'echo "  ok   - {name}"\n' for name in names) + "exit 0\n"
    patch_path = tmp_path / "tamper.patch"
    patch_path.write_text(_git_style_patch(rel, show.stdout, stub, tmp_path))
    code, payload = _run(task_id, patch_path, _env())
    assert payload.get("error") is None, payload.get("error")
    assert payload["resolved"] is False
    assert payload["f2p_pass"] is False
    assert rel in payload["reverted_test_edits"]
    assert code == 1


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
