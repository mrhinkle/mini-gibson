"""Computational (deterministic) sensors for the Gibson verifier.

These are the only things that certify completion:
  1. test files are unchanged (checksums before vs after the agent's run)
  2. the HARNESS reruns the test command itself and reads the exit code

Never trust the agent's own report of a test run. Standard library only.
"""
from __future__ import annotations

import fnmatch
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TEST_GLOBS = ["tests/*", "test/*", "**/__tests__/*", "*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go"]


def _is_test(rel: str, globs: list[str]) -> bool:
    name = Path(rel).name
    return any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(name, g) for g in globs)


def checksum_tests(repo: str | Path, globs: list[str] | None = None) -> dict[str, str]:
    """sha256 of every test file under repo (skips .git and node_modules)."""
    globs = globs or DEFAULT_TEST_GLOBS
    root = Path(repo)
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts or "node_modules" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        if _is_test(rel, globs):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def diff_checksums(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {
        "modified": sorted(k for k in before if k in after and before[k] != after[k]),
        "deleted": sorted(k for k in before if k not in after),
        "added": sorted(k for k in after if k not in before),
    }


@dataclass
class EnvResult:
    passed: bool
    exit_code: int
    output_tail: str
    timed_out: bool = False


def run_tests(repo: str | Path, command: list[str], timeout: int = 900) -> EnvResult:
    """The harness runs the tests itself. Argv list, no shell, no secrets in argv."""
    try:
        r = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr)[-4000:]
        return EnvResult(r.returncode == 0, r.returncode, out)
    except subprocess.TimeoutExpired as e:
        tail = ((e.stdout or "") + (e.stderr or ""))[-4000:] if isinstance(e.stdout, str) else ""
        return EnvResult(False, -1, tail, timed_out=True)


def tests_unchanged(before: dict[str, str], after: dict[str, str], allow_added: bool = True) -> bool:
    """Modified or deleted test files fail. New test files are allowed by default (adding coverage is fine)."""
    d = diff_checksums(before, after)
    return not d["modified"] and not d["deleted"] and (allow_added or not d["added"])
