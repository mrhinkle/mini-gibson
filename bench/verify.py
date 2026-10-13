#!/usr/bin/env python3
"""Verify one Gibson Bench v0.1 candidate patch.

Usage:
    python3 bench/verify.py TASK_ID CANDIDATE_PATCH

Prints a single JSON object on stdout:

    {"resolved": bool, "f2p_pass": bool, "p2p_pass": bool,
     "reverted_test_edits": [str], "logs_path": str}

Exit 0 only when the candidate is resolved. A side passes only when every
named id passed, every command for that side exited 0, the vitest report
was written when the runner is vitest, and every ``::__suite__`` status from
those commands is passed. A non-zero exit, a timeout, or a missing report
does not pass. Exit 1 otherwise.

Setup failures (missing mirror, unknown commit, patch that will not apply,
setup command failure, unreadable runner output, time-budget expiry) set
"error" and "resolved": false. A setup failure is never reported as resolved.
A missing vitest report is not a setup error: that command does not pass.

Environment (never written into task files):
    GIBSON_BENCH_MIRRORS        JSON map of repo name -> local git checkout
    GIBSON_BENCH_NODE_MODULES   optional JSON map of repo name -> node_modules
                                directory to link into the eval worktree

Tokens substituted in task commands and setup lines:
    <repo-root>   the temporary worktree
    <mirror>      the local checkout for this task's repo
    <logs>        the directory logs_path points at
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
TASKS_DIR = BENCH_DIR / "tasks"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
OK_RE = re.compile(r"^\s*ok\s+[—–\-]+\s+(.*\S)\s*$")
FAIL_RE = re.compile(r"^\s*(?:FAIL|NOT OK)\s+[—–\-]+\s+(.*\S)\s*$", re.I)


class SetupError(Exception):
    """The eval could not be executed. Never means the candidate resolved."""


_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}")
_SHA = re.compile(r"[0-9a-f]{40}")
_LOG_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,64}")


def _checked(pattern: re.Pattern[str], value: str, message: str) -> str:
    matched = pattern.fullmatch(value or "")
    if not matched:
        raise SetupError(message)
    return matched.group(0)


def _contained(root: Path, name: str) -> Path:
    """A direct child of root. The name cannot climb out of the directory."""
    safe = _checked(_LOG_NAME, name, "path name is not safe")
    base = root.resolve()
    dest = (base / safe).resolve()
    try:
        dest.relative_to(base)
    except ValueError as exc:
        raise SetupError("path escapes its directory") from exc
    return dest


def _temp_dir(prefix: str) -> Path:
    safe_prefix = _checked(re.compile(r"[A-Za-z0-9-]{1,40}"), prefix, "temp prefix is not safe")
    root = Path("/tmp").resolve()
    created = Path(tempfile.mkdtemp(prefix=f"{safe_prefix}-", dir=str(root))).resolve()
    try:
        created.relative_to(root)
    except ValueError as exc:
        shutil.rmtree(created, ignore_errors=True)
        raise SetupError("temp directory escaped /tmp") from exc
    return created


def _candidate_file(raw: str) -> Path:
    # The caller names a patch file. Accept only a relative-component-free path
    # of ordinary characters, then require it to be a regular file.
    matched = re.fullmatch(r"[A-Za-z0-9_./+-]{1,512}", raw or "")
    if not matched:
        raise SetupError("candidate patch does not exist")
    safe = matched.group(0)
    if ".." in safe.split("/"):
        raise SetupError("candidate patch does not exist")
    resolved = Path(safe).resolve()
    if not resolved.is_file():
        raise SetupError("candidate patch does not exist")
    return resolved


def _read_json_env(name: str) -> dict:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SetupError(f"{name} is not valid JSON") from exc
    if not isinstance(data, dict):
        raise SetupError(f"{name} must be a JSON object")
    return data


def _load_task(task_id: str) -> dict:
    safe_id = _checked(_TASK_ID, task_id, "task id is not a safe path component")
    root = TASKS_DIR.resolve()
    path = _contained(root, safe_id) / "task.json"
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise SetupError("task id escapes the task directory") from exc
    if not path.is_file():
        raise SetupError(f"unknown task {safe_id}")
    try:
        task = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SetupError(f"task.json is not valid JSON: {exc}") from exc
    for key in ("repo", "base_sha", "f2p", "p2p"):
        if key not in task:
            raise SetupError(f"task.json missing {key}")
    task["base_sha"] = _checked(_SHA, str(task["base_sha"]), "base_sha is not a full commit sha")
    task["repo"] = _checked(
        re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,40}"),
        str(task["repo"]),
        "repo name is not a safe path component",
    )
    return task


def _subst(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(key, value)
    if "<" in text and re.search(r"<(repo-root|mirror|logs|node-modules)>", text):
        raise SetupError("unsubstituted path token in a command")
    return text


def _git(mirror: Path, args: list[str], *, timeout: int = 180, input_text: str | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("FORCE_COLOR", None)
    env["NO_COLOR"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", "-C", str(mirror), *args],
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise SetupError(f"git {' '.join(args[:3])} timed out") from exc
    except OSError as exc:
        raise SetupError(f"git could not be started: {exc}") from exc


def _apply(worktree: Path, patch: str, *, allow_already: bool) -> None:
    if not patch.strip():
        return
    check = _git(worktree, ["apply", "--check", "--whitespace=nowarn", "-"], input_text=patch, timeout=60)
    if check.returncode == 0:
        applied = _git(worktree, ["apply", "--whitespace=nowarn", "-"], input_text=patch, timeout=60)
        if applied.returncode != 0:
            raise SetupError(f"patch failed to apply: {(applied.stderr or '')[-500:]}")
        return
    if allow_already:
        reverse = _git(
            worktree, ["apply", "--reverse", "--check", "--whitespace=nowarn", "-"],
            input_text=patch, timeout=60,
        )
        if reverse.returncode == 0:
            return
    detail = (check.stderr or check.stdout or "")[-500:]
    raise SetupError(f"patch failed to apply: {detail}")


def _link_node_modules(worktree: Path, repo: str) -> None:
    mapping = _read_json_env("GIBSON_BENCH_NODE_MODULES")
    source = mapping.get(repo)
    if not source:
        return
    src = Path(source)
    if not src.is_dir():
        raise SetupError(f"node_modules for {repo} is not a directory")
    dest = worktree / "node_modules"
    if dest.exists() or dest.is_symlink():
        return
    dest.symlink_to(src)


def _run_setup(worktree: Path, task: dict, mapping: dict[str, str]) -> None:
    for command in task.get("setup") or []:
        if not isinstance(command, str) or not command.strip():
            raise SetupError("setup command is empty")
        rendered = _subst(command, mapping)
        result = _run_command(rendered, worktree, mapping["<logs>"], timeout=120)
        if result["returncode"] != 0:
            raise SetupError(
                f"setup command failed ({result['returncode']}): {rendered[:200]}"
            )


def _run_command(command: str, cwd: Path, logs: str, *, timeout: int) -> dict:
    env = os.environ.copy()
    env.pop("FORCE_COLOR", None)
    env["NO_COLOR"] = "1"
    env["NODE_ENV"] = "test"
    # The scored command must not see host credentials.
    for key in list(env):
        upper = key.upper()
        if any(part in upper for part in ("TOKEN", "SECRET", "PASSWORD", "DATABASE_URL", "POSTGRES", "API_KEY", "OPENROUTER")):
            env.pop(key, None)
    log_dir = Path(logs).resolve()
    try:
        log_dir.relative_to(Path("/tmp").resolve())
    except ValueError as exc:
        raise SetupError("log directory escaped /tmp") from exc
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen(
            ["bash", "-c", command],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        raise SetupError(f"could not start command: {exc}") from exc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_group(proc)
        raise SetupError(f"time budget exceeded ({timeout}s)") from exc
    return {
        "returncode": proc.returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
    }


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, 15)
    except OSError:
        proc.kill()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()
        proc.communicate(timeout=5)


def _vitest_statuses(report_path: Path, worktree: Path) -> dict[str, str]:
    if not report_path.is_file():
        raise SetupError("vitest did not write a JSON report")
    try:
        report = json.loads(report_path.read_text())
    except json.JSONDecodeError as exc:
        raise SetupError("vitest JSON report is unreadable") from exc
    statuses: dict[str, str] = {}
    for file_rec in report.get("testResults") or []:
        raw_name = file_rec.get("name") or ""
        rel = raw_name
        try:
            rel = str(Path(raw_name).resolve().relative_to(worktree.resolve()))
        except Exception:
            for marker in ("tests/unit/", "tests/spec/", "scripts/tests/"):
                index = raw_name.find(marker)
                if index >= 0:
                    rel = raw_name[index:]
                    break
        assertions = file_rec.get("assertionResults") or []
        if not assertions:
            state = "passed" if file_rec.get("status") == "passed" else "failed"
            statuses[f"{rel}::__collect__"] = state
            continue
        for assertion in assertions:
            full = assertion.get("fullName") or assertion.get("title") or "unnamed"
            state = assertion.get("status") or "failed"
            if state not in ("passed", "failed"):
                state = "failed"
            statuses[f"{rel}::{full}"] = state
    return statuses


def _shell_statuses(text: str, command: str, returncode: int) -> dict[str, str]:
    clean = ANSI.sub("", text)
    match = re.search(r"(scripts/tests/\S+?\.test\.sh)", command)
    prefix = match.group(1) if match else "shell"
    statuses: dict[str, str] = {}
    for line in clean.splitlines():
        ok = OK_RE.match(line)
        if ok:
            name = ok.group(1).strip()
            statuses[f"{prefix}::{name}"] = "passed"
            statuses[name] = "passed"
            continue
        bad = FAIL_RE.match(line)
        if bad:
            name = bad.group(1).strip()
            # A later duplicate name must not promote a failure back to a pass.
            statuses[f"{prefix}::{name}"] = "failed"
            statuses[name] = "failed"
    named_failed = any(state != "passed" for state in statuses.values())
    statuses[f"{prefix}::__suite__"] = "passed" if returncode == 0 and not named_failed else "failed"
    return statuses


def _command_statuses(task: dict, command: str, result: dict, worktree: Path, logs: Path) -> tuple[dict[str, str], bool]:
    """Return parsed statuses and whether the vitest report was missing.

    A missing report is a failed command, not a setup error. Unreadable JSON
    still raises SetupError.
    """
    runner = task.get("runner") or "vitest"
    combined = result["stdout"] + "\n" + result["stderr"]
    _contained(logs, "command.log").write_text(
        f"$ {command}\nexit={result['returncode']}\n{combined[-200000:]}"
    )
    if runner == "shell":
        return _shell_statuses(combined, command, result["returncode"]), False
    report = _contained(logs, "vitest.json")
    if not report.is_file():
        return {}, True
    return _vitest_statuses(report, worktree), False


def _ids_pass(statuses: dict[str, str], ids: list[str]) -> bool:
    if not isinstance(ids, list):
        raise SetupError("test id list is not a list")
    for test_id in ids:
        if statuses.get(test_id) == "passed":
            continue
        _prefix, sep, name = test_id.partition("::")
        if sep and statuses.get(name) == "passed":
            continue
        return False
    return True


DEFAULT_TEST_GLOBS = ("**/*.test.*", "**/tests/**", "scripts/tests/**")


def _glob_match(path: str, pattern: str) -> bool:
    """Match a repo-relative path. ``**`` crosses directories, including none."""
    path = path.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/")
    pieces: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            pieces.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            pieces.append(".*")
            index += 2
        elif pattern[index] == "*":
            pieces.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(pattern[index]))
            index += 1
    return re.fullmatch("".join(pieces), path) is not None


def _matches_test_glob(path: str, patterns: list[str]) -> bool:
    return any(_glob_match(path, pattern) for pattern in patterns)


def _safe_rel(path: str) -> str | None:
    path = (path or "").strip()
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return None
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return path


def _patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split(" ")
        if len(parts) < 4:
            continue
        name = parts[-1]
        if name.startswith("b/"):
            name = name[2:]
        safe = _safe_rel(name)
        if safe:
            paths.append(safe)
    return paths


def _candidate_paths(worktree: Path) -> list[str]:
    diff = _git(worktree, ["diff", "--name-status", "HEAD"])
    untracked = _git(worktree, ["ls-files", "--others", "--exclude-standard"])
    if diff.returncode != 0:
        raise SetupError(f"could not list candidate edits: {(diff.stderr or '')[-300:]}")
    if untracked.returncode != 0:
        raise SetupError(f"could not list untracked files: {(untracked.stderr or '')[-300:]}")
    found: list[str] = []
    for line in diff.stdout.splitlines():
        bits = line.split("\t")
        for path in bits[1:]:
            safe = _safe_rel(path)
            if safe:
                found.append(safe)
    for path in untracked.stdout.splitlines():
        safe = _safe_rel(path)
        if safe:
            found.append(safe)
    unique: list[str] = []
    seen: set[str] = set()
    for path in found:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _revert_path(worktree: Path, rel: str) -> None:
    target = (worktree / rel).resolve()
    try:
        target.relative_to(worktree.resolve())
    except ValueError as exc:
        raise SetupError("test path escapes the worktree") from exc
    tracked = _git(worktree, ["cat-file", "-e", f"HEAD:{rel}"])
    if tracked.returncode == 0:
        restored = _git(worktree, ["checkout", "HEAD", "--", rel])
        if restored.returncode != 0:
            raise SetupError(f"could not restore {rel}")
        return
    if target.is_file() or target.is_symlink():
        target.unlink()
        return
    if target.exists():
        raise SetupError(f"could not restore {rel}")


def _revert_test_edits(worktree: Path, changed: list[str], test_patch: str, test_globs: list[str]) -> list[str]:
    protected = set(_patch_paths(test_patch))
    reverted: list[str] = []
    for rel in changed:
        if rel in protected or _matches_test_glob(rel, test_globs):
            _revert_path(worktree, rel)
            reverted.append(rel)
    return sorted(set(reverted))


def _test_globs(task: dict) -> list[str]:
    raw = task.get("test_globs")
    if raw is None:
        return list(DEFAULT_TEST_GLOBS)
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise SetupError("test_globs is not a list of strings")
    return list(raw)


def score_sides(
    statuses: dict[str, str],
    f2p_ids: list[str],
    p2p_ids: list[str],
    records: list[dict],
) -> dict[str, bool]:
    """A side passes when its ids passed and each of its commands exited cleanly."""

    def side_passes(side: str, ids: list[str]) -> bool:
        if side == "f2p" and not ids:
            return False
        for record in records:
            if side not in record.get("sides", ()):
                continue
            if record.get("timed_out") or record.get("missing_report"):
                return False
            if record.get("returncode") != 0:
                return False
            for key, state in (record.get("statuses") or {}).items():
                if str(key).endswith("::__suite__") and state != "passed":
                    return False
        return _ids_pass(statuses, ids)

    f2p_pass = side_passes("f2p", f2p_ids)
    p2p_pass = side_passes("p2p", p2p_ids)
    return {
        "f2p_pass": f2p_pass,
        "p2p_pass": p2p_pass,
        "resolved": bool(f2p_pass and p2p_pass),
    }


def _prepare_worktree(task: dict, logs: Path) -> tuple[Path, Path]:
    mirrors = _read_json_env("GIBSON_BENCH_MIRRORS")
    repo = task["repo"]
    mirror_raw = mirrors.get(repo)
    if not mirror_raw:
        raise SetupError(f"no mirror configured for {repo}")
    mirror = Path(mirror_raw)
    if not mirror.exists():
        raise SetupError(f"mirror for {repo} does not exist")
    if _git(mirror, ["rev-parse", "--verify", "--quiet", f"{task['base_sha']}^{{commit}}"]).returncode != 0:
        raise SetupError("base commit is not in the mirror")
    parent = _temp_dir("gibson-bench")
    worktree = _contained(parent, "repo")
    added = _git(mirror, ["worktree", "add", "--detach", str(worktree), task["base_sha"]], timeout=300)
    if added.returncode != 0:
        shutil.rmtree(parent, ignore_errors=True)
        raise SetupError(f"could not check out base: {(added.stderr or '')[-500:]}")
    try:
        _link_node_modules(worktree, repo)
        mapping = {
            "<repo-root>": str(worktree),
            "<mirror>": str(mirror),
            "<logs>": str(logs),
        }
        _run_setup(worktree, task, mapping)
    except Exception:
        _remove_worktree(mirror, worktree, parent)
        raise
    return worktree, mirror


def _remove_worktree(mirror: Path, worktree: Path, parent: Path) -> None:
    if worktree.exists():
        _git(mirror, ["worktree", "remove", "--force", str(worktree)], timeout=180)
    shutil.rmtree(parent, ignore_errors=True)
    _git(mirror, ["worktree", "prune"], timeout=60)


def verify(task_id: str, candidate_patch: Path) -> dict:
    logs = _temp_dir("gibson-bench-logs")
    result = {
        "resolved": False,
        "f2p_pass": False,
        "p2p_pass": False,
        "reverted_test_edits": [],
        "logs_path": str(logs),
    }
    worktree = None
    mirror = None
    parent = None
    try:
        candidate_patch = _candidate_file(str(candidate_patch))
        task = _load_task(task_id)
        candidate = candidate_patch.read_text(errors="replace")
        test_patch_path = _contained(TASKS_DIR.resolve(), task_id) / "test.patch"
        try:
            test_patch_path.resolve().relative_to(TASKS_DIR.resolve())
        except ValueError as exc:
            raise SetupError("test.patch escapes the task directory") from exc
        if not test_patch_path.is_file():
            raise SetupError("test.patch is missing")
        test_patch = test_patch_path.read_text(errors="replace")
        worktree, mirror = _prepare_worktree(task, logs)
        parent = worktree.parent
        # Apply the candidate, restore any test file it changed back to the
        # base blob, then apply the hidden test.patch. A candidate that only
        # edits tests therefore runs the original failing tests.
        _apply(worktree, candidate, allow_already=False)
        changed = _candidate_paths(worktree)
        result["reverted_test_edits"] = _revert_test_edits(
            worktree, changed, test_patch, _test_globs(task),
        )
        _apply(worktree, test_patch, allow_already=True)
        f2p = task["f2p"]
        p2p = task["p2p"]
        command_sides: dict[str, list[str]] = {}
        commands: list[str] = []
        for side, group in (("f2p", f2p), ("p2p", p2p)):
            for command in group.get("commands") or []:
                if command not in command_sides:
                    command_sides[command] = []
                    commands.append(command)
                if side not in command_sides[command]:
                    command_sides[command].append(side)
        if not commands:
            raise SetupError("task has no commands")
        budget = int(task.get("time_budget_s") or 300)
        if budget < 1 or budget > 300:
            raise SetupError("time_budget_s must be between 1 and 300")
        mapping = {
            "<repo-root>": str(worktree),
            "<mirror>": str(mirror),
            "<logs>": str(logs),
        }
        statuses: dict[str, str] = {}
        records: list[dict] = []
        for index, command in enumerate(commands):
            rendered = _subst(command, mapping)
            index_name = _checked(re.compile(r"[0-9]{1,2}"), str(index), "command index is not safe")
            _contained(logs, f"command-{index_name}.txt").write_text(rendered + "\n")
            # Drop the previous vitest report so a later command cannot inherit it.
            report = _contained(logs, "vitest.json")
            if index and report.exists():
                shutil.copyfile(report, _contained(logs, f"vitest-{index_name}.json"))
                report.unlink()
            ran = _run_command(rendered, worktree, str(logs), timeout=budget)
            _contained(logs, f"stdout-{index_name}.log").write_text(ran["stdout"][-200000:])
            _contained(logs, f"stderr-{index_name}.log").write_text(ran["stderr"][-200000:])
            found, missing_report = _command_statuses(task, rendered, ran, worktree, logs)
            statuses.update(found)
            records.append({
                "sides": command_sides[command],
                "returncode": ran["returncode"],
                "timed_out": False,
                "missing_report": missing_report,
                "statuses": found,
            })
        f2p_ids = list(f2p.get("test_ids") or [])
        p2p_ids = list(p2p.get("test_ids") or [])
        if not f2p_ids:
            raise SetupError("task has no fail-to-pass ids")
        result.update(score_sides(statuses, f2p_ids, p2p_ids, records))
        _contained(logs, "statuses.json").write_text(json.dumps(statuses, indent=2, sort_keys=True))
    except SetupError as exc:
        result["resolved"] = False
        result["f2p_pass"] = False
        result["p2p_pass"] = False
        result["error"] = str(exc)
    except Exception as exc:
        result["resolved"] = False
        result["f2p_pass"] = False
        result["p2p_pass"] = False
        result["error"] = f"setup failed: {type(exc).__name__}: {exc}"
    finally:
        if worktree is not None and mirror is not None and parent is not None:
            try:
                _remove_worktree(mirror, worktree, parent)
            except Exception as exc:
                # A cleanup failure must not flip a real failure into resolved.
                result["resolved"] = False
                result["error"] = result.get("error") or f"cleanup failed: {exc}"
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            json.dumps({
                "resolved": False,
                "f2p_pass": False,
                "p2p_pass": False,
                "logs_path": "",
                "error": "usage: python3 bench/verify.py TASK_ID CANDIDATE_PATCH",
            })
        )
        return 1
    try:
        task_id = _checked(_TASK_ID, argv[1], "task id is not a safe path component")
        patch = _candidate_file(argv[2])
    except SetupError as exc:
        print(json.dumps({
            "resolved": False,
            "f2p_pass": False,
            "p2p_pass": False,
            "logs_path": "",
            "error": str(exc),
        }))
        return 1
    result = verify(task_id, patch)
    print(json.dumps(result))
    return 0 if result.get("resolved") is True and "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
