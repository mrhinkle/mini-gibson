"""Qualification verifier for pinned SWE-rebench task images.

This module handles hidden verifier material on the trusted host.  It is not an
agent entrypoint.  Qualification requires two independent base failures and two
independent gold successes, each in a fresh container.
"""

from __future__ import annotations

import hashlib
import inspect
import io
import re
import shlex
import sys
import tarfile
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

from .cohort import SUPPORTED_LOG_PARSERS, dump_canonical_json
from .docker_backend import (
    IMAGE_RE,
    DockerBackend,
    DockerIsolationError,
    DockerRunResult,
)

RECEIPT_SCHEMA = "mini-gibson-rebench-qualification/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STATUS_VALUES = {"passed", "failed", "error", "skipped"}
MARKER_PREFIX = "__MINI_GIBSON_VERIFIER_V1__"
ERROR_MAX_UTF8_BYTES = 2000
ERROR_TRUNCATION_MARKER = "... [truncated]"
HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?: .*)?$"
)


class RebenchVerificationError(ValueError):
    """Verifier input is unsafe or internally inconsistent."""


ParserCallable = Callable[[str], Mapping[str, str]]
_PINNED_PARSER_TOKEN = object()


class _PinnedTestStatus(str, Enum):
    """Exact public status contract imported by the pinned upstream parsers."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


def _sealed_parser_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    """Resolve the upstream parser's sole project-local import without shadowing.

    SWE-rebench V2's pinned ``log_parsers.py`` imports ``TestStatus`` from its
    adjacent ``swe_constants.py``.  The four enum values are reproduced here
    so the *unmodified* upstream parser file can be hash-bound and executed
    outside an SWE-rebench checkout.  Every other import uses Python's normal
    importer.  This compatibility code is itself covered by the verifier hash
    recorded in the qualification journal.
    """

    if level == 0 and name == "lib.agent.swe_constants":
        module = type(sys)("lib.agent.swe_constants")
        module.TestStatus = _PinnedTestStatus
        return module
    return __import__(name, globals, locals, fromlist, level)


class PinnedParser:
    """A parser callable loaded from the exact source bytes named by its hash."""

    __slots__ = ("name", "source_sha256", "_callable", "_sealed")

    def __init__(
        self,
        name: str,
        source_sha256: str,
        parser: ParserCallable,
        *,
        _token: object,
    ) -> None:
        if _token is not _PINNED_PARSER_TOKEN:
            raise RebenchVerificationError("PinnedParser must be created by a pinned parser loader")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "source_sha256", source_sha256)
        object.__setattr__(self, "_callable", parser)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, _name: str, _value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("PinnedParser is immutable")
        object.__setattr__(self, _name, _value)

    def __call__(self, output: str) -> Mapping[str, str]:
        return self._callable(output)


@dataclass(frozen=True)
class QualificationTask:
    instance_id: str
    image_reference: str
    image_digest: str
    workdir: str
    verify_timeout_s: int = 900


@dataclass(frozen=True)
class VerifierMaterial:
    gold_patch: str
    test_patch: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    test_command: str
    parser_name: str
    parser_sha256: str


@dataclass(frozen=True)
class ScoredRun:
    phase: str
    repeat: int
    expectation_met: bool
    returncode: int | None
    timed_out: bool
    output_truncated: bool
    parser_ok: bool
    integrity_ok: bool
    fail_to_pass_states: Mapping[str, str]
    pass_to_pass_states: Mapping[str, str]
    stdout_sha256: str
    stderr_sha256: str
    stdout_head_sha256: str
    stdout_tail_sha256: str
    stderr_head_sha256: str
    stderr_tail_sha256: str
    stdout_captured_bytes: int
    stderr_captured_bytes: int
    command_sha256: str
    error: str | None


def load_pinned_parser_bytes(
    source: bytes,
    parser_name: str,
    expected_sha256: str,
) -> PinnedParser:
    """Compile a parser only after hashing the exact source bytes executed."""

    if parser_name not in SUPPORTED_LOG_PARSERS:
        raise RebenchVerificationError("parser_name is not in the frozen allowlist")
    if not SHA256_RE.fullmatch(expected_sha256):
        raise RebenchVerificationError("expected parser hash must be a lowercase SHA-256")
    if _sha256(source) != expected_sha256:
        raise RebenchVerificationError("pinned parser bytes do not match parser_sha256")
    module_name = f"_mini_gibson_rebench_parser_{expected_sha256[:16]}"
    module = type(sys)(module_name)
    module.__file__ = f"<sealed-parser:{expected_sha256}>"
    builtins = dict(vars(__import__("builtins")))
    builtins["__import__"] = _sealed_parser_import
    module.__dict__["__builtins__"] = builtins
    try:
        code = compile(source, module.__file__, "exec")
        exec(code, module.__dict__)
    except Exception as exc:
        raise RebenchVerificationError(f"could not load pinned parser: {type(exc).__name__}: {exc}") from exc
    parser = getattr(module, parser_name, None)
    if not inspect.isfunction(parser):
        raise RebenchVerificationError(f"pinned parser must directly define function {parser_name}")
    if parser.__code__.co_filename != module.__file__ or parser.__globals__ is not module.__dict__:
        raise RebenchVerificationError("pinned parser callable is not defined by the hashed source bytes")
    return PinnedParser(
        parser_name,
        expected_sha256,
        parser,
        _token=_PINNED_PARSER_TOKEN,
    )


def load_pinned_parser(
    parser_path: str | Path,
    parser_name: str,
    expected_sha256: str,
) -> PinnedParser:
    """Load one allowlisted parser from exact hash-bound source bytes.

    The parser source can be unpacked from the sealed verifier package.  It is
    loaded by file path, not normal module lookup, so an installed package with
    the same name cannot silently shadow it.
    """

    path = Path(parser_path)
    if parser_name not in SUPPORTED_LOG_PARSERS:
        raise RebenchVerificationError("parser_name is not in the frozen allowlist")
    if not SHA256_RE.fullmatch(expected_sha256):
        raise RebenchVerificationError("expected parser hash must be a lowercase SHA-256")
    if not path.is_file() or path.is_symlink():
        raise RebenchVerificationError("pinned parser must be a regular non-symlink file")
    return load_pinned_parser_bytes(path.read_bytes(), parser_name, expected_sha256)


def _sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def _validate_task(task: QualificationTask) -> None:
    if not task.instance_id or any(char in task.instance_id for char in "\0\r\n"):
        raise RebenchVerificationError("instance_id must be a single non-empty line")
    if not IMAGE_RE.fullmatch(task.image_reference):
        raise RebenchVerificationError("image_reference must be pinned by immutable digest")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", task.image_digest):
        raise RebenchVerificationError("image_digest must be sha256:<64 hex>")
    if not task.image_reference.endswith(f"@{task.image_digest}"):
        raise RebenchVerificationError("image reference and digest disagree")
    workdir = PurePosixPath(task.workdir)
    if not task.workdir.startswith("/") or task.workdir == "/" or ".." in workdir.parts:
        raise RebenchVerificationError("workdir must be a safe absolute path")
    if task.verify_timeout_s != 900:
        raise RebenchVerificationError("qualification timeout must equal the frozen 900 seconds")


def _validate_ids(values: Sequence[str], name: str, *, required: bool) -> None:
    if required and not values:
        raise RebenchVerificationError(f"{name} must not be empty")
    if len(set(values)) != len(values):
        raise RebenchVerificationError(f"{name} contains duplicates")
    if not all(isinstance(item, str) and item and not set(item) & {"\0", "\r", "\n"} for item in values):
        raise RebenchVerificationError(f"{name} must contain non-empty single-line strings")


def _validate_material(material: VerifierMaterial) -> None:
    if not material.gold_patch.strip() or not material.test_patch.strip():
        raise RebenchVerificationError("gold_patch and test_patch must not be empty")
    if not material.test_command.strip() or "\0" in material.test_command:
        raise RebenchVerificationError("test_command must be non-empty and contain no NUL")
    if material.parser_name not in SUPPORTED_LOG_PARSERS:
        raise RebenchVerificationError("parser_name is not in the frozen allowlist")
    if not SHA256_RE.fullmatch(material.parser_sha256):
        raise RebenchVerificationError("parser_sha256 must be a lowercase SHA-256")
    _validate_ids(material.fail_to_pass, "fail_to_pass", required=True)
    _validate_ids(material.pass_to_pass, "pass_to_pass", required=False)


def _safe_patch_path(
    raw: str,
    *,
    expected_prefix: str | None,
    allow_dev_null: bool = False,
) -> str | None:
    if raw == "/dev/null":
        if allow_dev_null:
            return None
        raise RebenchVerificationError("patch path cannot be /dev/null here")
    if (
        not raw
        or raw.startswith("/")
        or "\\" in raw
        or any(ord(char) < 32 or ord(char) == 127 for char in raw)
    ):
        raise RebenchVerificationError(f"patch contains unsafe path {raw!r}")
    if expected_prefix is not None:
        prefix = f"{expected_prefix}/"
        if not raw.startswith(prefix):
            raise RebenchVerificationError(
                f"patch path must use canonical {prefix!r} prefix: {raw!r}"
            )
        raw = raw[len(prefix) :]
    # Split the original spelling instead of using PurePosixPath, which
    # silently collapses empty and '.' components.  Aliases such as
    # './conftest.py' must not evade overlap with 'conftest.py'.
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise RebenchVerificationError(f"patch contains noncanonical path {raw!r}")
    if parts[0] == ".git":
        raise RebenchVerificationError(f"patch contains forbidden path {raw!r}")
    canonical = "/".join(parts)
    if canonical != raw:
        raise RebenchVerificationError(f"patch contains noncanonical path {raw!r}")
    return canonical


def _quoted_or_raw_path(
    raw: str,
    context: str,
    *,
    allow_trailing_git_tab: bool = False,
) -> str:
    """Parse one Git path, retaining legal unquoted spaces in metadata."""

    # Git may terminate an unquoted ---/+++ pathname with a single tab even
    # when it emits no timestamp.  Treat only that exact suffix as syntax;
    # embedded tabs remain ambiguous and fail closed.
    if allow_trailing_git_tab and raw.endswith("\t") and raw.count("\t") == 1:
        raw = raw[:-1]
    if (
        not raw
        or raw != raw.strip()
        or "\\" in raw
        or any(ord(char) < 32 or ord(char) == 127 for char in raw)
    ):
        raise RebenchVerificationError(f"patch contains ambiguous {context} path")
    value = raw
    if not value:
        raise RebenchVerificationError(f"patch contains empty {context} path")
    if value.startswith('"'):
        try:
            parts = shlex.split(value)
        except ValueError as exc:
            raise RebenchVerificationError(f"patch contains malformed quoted {context} path") from exc
        if len(parts) != 1:
            raise RebenchVerificationError(f"patch contains ambiguous quoted {context} path")
        return parts[0]
    return value


def _diff_header_paths(line: str) -> tuple[str, str]:
    """Parse canonical ``diff --git a/... b/...`` paths fail closed.

    Git does not always quote pathnames containing spaces.  In that form the
    canonical `` b/`` boundary is safe only when it has exactly one possible
    interpretation; multiple candidates are rejected instead of guessed.
    """

    body = line[len("diff --git ") :]
    if (
        not body
        or "\\" in body
        or any(ord(char) < 32 or ord(char) == 127 for char in body)
    ):
        raise RebenchVerificationError("patch contains noncanonical diff header path")

    if body.startswith('"'):
        try:
            raw_paths = shlex.split(body)
        except ValueError as exc:
            raise RebenchVerificationError("patch contains malformed diff header") from exc
        if len(raw_paths) != 2:
            raise RebenchVerificationError("patch contains malformed diff header")
        old_path = _safe_patch_path(raw_paths[0], expected_prefix="a")
        new_path = _safe_patch_path(raw_paths[1], expected_prefix="b")
        assert old_path is not None and new_path is not None
        return old_path, new_path

    candidates: list[tuple[str, str]] = []
    cursor = 0
    while True:
        boundary = body.find(" b/", cursor)
        if boundary < 0:
            break
        try:
            old_path = _safe_patch_path(body[:boundary], expected_prefix="a")
            new_path = _safe_patch_path(body[boundary + 1 :], expected_prefix="b")
        except RebenchVerificationError:
            pass
        else:
            assert old_path is not None and new_path is not None
            candidates.append((old_path, new_path))
        cursor = boundary + 1
    if len(candidates) != 1:
        raise RebenchVerificationError("patch contains malformed or ambiguous diff header")
    return candidates[0]


def _finalize_patch_section(section: Mapping[str, object], paths: set[str]) -> None:
    old_path, new_path = section["diff"]  # type: ignore[misc]
    paths.update(path for path in (old_path, new_path) if path is not None)

    minus = section["minus"]
    plus = section["plus"]
    minus_seen = section["minus_seen"]
    plus_seen = section["plus_seen"]
    if minus_seen != plus_seen:
        raise RebenchVerificationError("patch section must contain both --- and +++ headers")
    if minus_seen:
        if minus is None and plus is None:
            raise RebenchVerificationError("patch section cannot compare /dev/null to itself")
        if minus is not None and minus != old_path:
            raise RebenchVerificationError("--- path disagrees with diff --git source")
        if plus is not None and plus != new_path:
            raise RebenchVerificationError("+++ path disagrees with diff --git destination")
        paths.update(path for path in (minus, plus) if path is not None)

    rename_from = section["rename_from"]
    rename_to = section["rename_to"]
    copy_from = section["copy_from"]
    copy_to = section["copy_to"]
    has_rename = rename_from is not None or rename_to is not None
    has_copy = copy_from is not None or copy_to is not None
    if has_rename and has_copy:
        raise RebenchVerificationError("patch section cannot be both a rename and a copy")
    if (has_rename or has_copy) and minus_seen and (minus is None or plus is None):
        raise RebenchVerificationError("rename/copy content headers cannot use /dev/null")
    if has_rename:
        if rename_from is None or rename_to is None:
            raise RebenchVerificationError("rename metadata requires both from and to paths")
        if (rename_from, rename_to) != (old_path, new_path):
            raise RebenchVerificationError("rename metadata disagrees with diff --git paths")
        paths.update((rename_from, rename_to))
    elif has_copy:
        if copy_from is None or copy_to is None:
            raise RebenchVerificationError("copy metadata requires both from and to paths")
        if (copy_from, copy_to) != (old_path, new_path):
            raise RebenchVerificationError("copy metadata disagrees with diff --git paths")
        paths.update((copy_from, copy_to))
    elif old_path != new_path:
        raise RebenchVerificationError(
            "diff --git source and destination differ without matching rename/copy metadata"
        )


def _start_text_hunk(section: dict[str, object], line: str) -> None:
    if not section["minus_seen"] or not section["plus_seen"]:
        raise RebenchVerificationError("text hunk requires canonical --- and +++ headers")
    match = HUNK_HEADER_RE.fullmatch(line)
    if match is None:
        raise RebenchVerificationError("patch contains malformed hunk header")
    try:
        old_count = int(match.group("old_count") or "1")
        new_count = int(match.group("new_count") or "1")
    except ValueError as exc:
        raise RebenchVerificationError("patch contains invalid hunk line counts") from exc
    if old_count == 0 and new_count == 0:
        raise RebenchVerificationError("patch contains empty hunk")
    section["hunk_old_remaining"] = old_count
    section["hunk_new_remaining"] = new_count
    section["hunk_active"] = True
    section["hunk_seen"] = True
    section["allow_no_newline_marker"] = False


def _consume_hunk_line(section: dict[str, object], line: str) -> None:
    if line == r"\ No newline at end of file":
        if not section["allow_no_newline_marker"]:
            raise RebenchVerificationError("misplaced no-newline marker in patch hunk")
        section["allow_no_newline_marker"] = False
        return

    if not section["hunk_active"] or not line:
        raise RebenchVerificationError(
            "unexpected content after completed hunk; each file requires diff --git"
        )
    prefix = line[0]
    old_delta = 1 if prefix in {" ", "-"} else 0
    new_delta = 1 if prefix in {" ", "+"} else 0
    if prefix not in {" ", "-", "+"}:
        raise RebenchVerificationError("patch contains malformed or truncated hunk payload")

    old_remaining = int(section["hunk_old_remaining"])
    new_remaining = int(section["hunk_new_remaining"])
    if old_delta > old_remaining or new_delta > new_remaining:
        raise RebenchVerificationError("patch hunk payload exceeds declared line counts")
    old_remaining -= old_delta
    new_remaining -= new_delta
    section["hunk_old_remaining"] = old_remaining
    section["hunk_new_remaining"] = new_remaining
    section["hunk_active"] = old_remaining != 0 or new_remaining != 0
    section["allow_no_newline_marker"] = True


def patch_paths(patch: str) -> set[str]:
    """Return every effective path from a Git patch.

    All path-bearing lines are parsed, normalized, and reconciled by section.
    A safe ``diff --git`` header cannot hide an unsafe or protected rename/copy
    source in extended metadata.
    """

    paths: set[str] = set()
    section: dict[str, object] | None = None
    for line in patch.splitlines():
        if section is not None and section["hunk_active"]:
            _consume_hunk_line(section, line)
            continue
        if section is not None and line == r"\ No newline at end of file":
            _consume_hunk_line(section, line)
            continue
        if line.startswith("diff --git "):
            if section is not None:
                _finalize_patch_section(section, paths)
            old_path, new_path = _diff_header_paths(line)
            section = {
                "diff": (old_path, new_path),
                "minus": None,
                "plus": None,
                "minus_seen": False,
                "plus_seen": False,
                "rename_from": None,
                "rename_to": None,
                "rename_from_seen": False,
                "rename_to_seen": False,
                "copy_from": None,
                "copy_to": None,
                "copy_from_seen": False,
                "copy_to_seen": False,
                "hunk_seen": False,
                "hunk_active": False,
                "hunk_old_remaining": 0,
                "hunk_new_remaining": 0,
                "allow_no_newline_marker": False,
            }
            continue
        if line.startswith("@@"):
            if section is None:
                raise RebenchVerificationError("patch hunk appears before diff --git header")
            _start_text_hunk(section, line)
            continue
        if line == "GIT binary patch" or line.startswith("Binary files "):
            raise RebenchVerificationError("binary patches are unsupported for qualification")
        markers = (
            ("--- ", "minus", "a", True),
            ("+++ ", "plus", "b", True),
            ("rename from ", "rename_from", None, False),
            ("rename to ", "rename_to", None, False),
            ("copy from ", "copy_from", None, False),
            ("copy to ", "copy_to", None, False),
        )
        matched = next((item for item in markers if line.startswith(item[0])), None)
        if matched is None:
            if section is not None and section["hunk_seen"] and line:
                raise RebenchVerificationError(
                    "unexpected content after completed hunk; each file requires diff --git"
                )
            continue
        if section is None:
            raise RebenchVerificationError("patch path metadata appears before diff --git header")
        if section["hunk_seen"]:
            raise RebenchVerificationError(
                "header-only second file is forbidden; each file requires diff --git"
            )
        prefix, field, expected_prefix, allow_dev_null = matched
        seen_field = f"{field}_seen"
        if section[seen_field]:
            raise RebenchVerificationError(f"patch section contains duplicate {prefix.strip()} metadata")
        parsed = _quoted_or_raw_path(
            line[len(prefix) :],
            prefix.strip(),
            allow_trailing_git_tab=field in {"minus", "plus"},
        )
        section[field] = _safe_patch_path(
            parsed,
            expected_prefix=expected_prefix,
            allow_dev_null=allow_dev_null,
        )
        section[seen_field] = True

    if section is not None and section["hunk_active"]:
        raise RebenchVerificationError("patch ends before declared hunk line counts are exhausted")

    if section is not None:
        _finalize_patch_section(section, paths)
    if patch.strip() and section is None:
        raise RebenchVerificationError("patch has no git diff headers")
    return paths


def _looks_like_test_path(path: str) -> bool:
    folded = path.casefold()
    parts = PurePosixPath(folded).parts
    name = parts[-1]
    return (
        name in {"conftest.py", "pytest.ini", "tox.ini"}
        or any(part in {"test", "tests", "__tests__", "spec", "specs"} for part in parts[:-1])
        or name.startswith(("test_", "spec_"))
        or any(token in name for token in (".test.", ".spec.", "_test.", "_spec."))
    )


def protected_paths(gold_patch: str, test_patch: str) -> tuple[str, ...]:
    """Reject product patches that touch hidden or conventional test paths."""

    product = patch_paths(gold_patch)
    hidden = patch_paths(test_patch)
    overlap = product & hidden
    test_like = {path for path in product if _looks_like_test_path(path)}
    forbidden = sorted(overlap | test_like)
    if forbidden:
        raise RebenchVerificationError(f"product patch touches protected test paths: {forbidden}")
    return tuple(sorted(hidden))


def _tar_member(archive: tarfile.TarFile, name: str, data: bytes, mode: int = 0o600) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = 1000
    info.gid = 1000
    archive.addfile(info, io.BytesIO(data))


def _runner_script(marker_token: str) -> str:
    # The command itself is sealed input.  Candidate/model input never reaches
    # this script, and no patch content appears in argv or the receipt.
    return rf"""#!/usr/bin/env bash
set -u
stage="$(mktemp -d /tmp/mini-gibson-verifier.XXXXXX)" || exit 80
trap 'rm -rf "$stage"' EXIT
tar -xf - -C "$stage" || exit 81
cd "$PWD" || exit 82
test -d .git || exit 83
status_output="$(git status --porcelain=v1 --untracked-files=no)" || exit 84
test -z "$status_output" || exit 84
if test -s "$stage/product.patch"; then
  git apply -p1 --check --whitespace=nowarn "$stage/product.patch" || exit 85
  git apply -p1 --whitespace=nowarn "$stage/product.patch" || exit 86
fi
git apply -p1 --check --whitespace=nowarn "$stage/test.patch" || exit 87
git apply -p1 --whitespace=nowarn "$stage/test.patch" || exit 88

git ls-files > "$stage/tracked-files" || exit 92
awk '
  /(^|\/)(tests?|__tests__|specs?)(\/|$)/ ||
  /(^|\/)(test_|spec_)[^\/]*$/ ||
  /\.(test|spec)\.[^\/]*$/ ||
  /_(test|spec)\.[^\/]*$/ ||
  /(^|\/)(conftest\.py|pytest\.ini|tox\.ini)$/ {{ print }}
' "$stage/tracked-files" > "$stage/tracked-protected" || exit 93

: > "$stage/sealed-protected" || exit 94
while IFS= read -r path || test -n "$path"; do
  case "$path" in
    ""|/*|*/|*//*|.|./*|*/.|*/./*|..|../*|*/..|*/../*|.git|.git/*|*\\*) exit 94 ;;
  esac
  if [[ "$path" =~ [[:cntrl:]] ]]; then
    exit 94
  fi
  printf '%s\n' "$path" >> "$stage/sealed-protected" || exit 94
done < "$stage/protected-paths"

LC_ALL=C sort -u "$stage/tracked-protected" "$stage/sealed-protected" \
  > "$stage/all-protected" || exit 95

hash_protected() {{
  while IFS= read -r path; do
    test -n "$path" || continue
    if test -L "$path"; then
      printf 'link\t%s\t%s\n' "$path" "$(readlink "$path")"
    elif test -f "$path"; then
      printf 'file\t%s\t' "$path"
      sha256sum -- "$path"
    elif test -e "$path"; then
      printf 'other\t%s\n' "$path"
    else
      printf 'missing\t%s\n' "$path"
    fi
  done < "$stage/all-protected" | sha256sum | awk '{{print $1}}'
}}

before="$(hash_protected)" || exit 89
test_command="$(cat "$stage/test-command")" || exit 90
set +e
/bin/bash -lc "$test_command"
test_rc=$?
set -e
after="$(hash_protected)" || exit 91
printf '\n{MARKER_PREFIX}:{marker_token}:%s:%s:%s\n' "$test_rc" "$before" "$after" >&2
test "$before" = "$after" || exit 97
exit "$test_rc"
"""


def build_verifier_payload(
    *,
    product_patch: str,
    material: VerifierMaterial,
    protected: Sequence[str],
    marker_token: str,
) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        _tar_member(archive, "product.patch", product_patch.encode())
        _tar_member(archive, "test.patch", material.test_patch.encode())
        _tar_member(archive, "test-command", material.test_command.encode())
        path_bytes = ("\n".join(protected) + "\n").encode()
        _tar_member(archive, "protected-paths", path_bytes)
    # runner.sh is deliberately passed as argv, not included in the tar the
    # runner extracts; this prevents the input archive from replacing it.
    return buffer.getvalue()


def _integrity_marker(stderr: str, token: str) -> tuple[bool, str | None]:
    prefix = f"{MARKER_PREFIX}:{token}:"
    matches = [line for line in stderr.splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        return False, "missing or duplicate verifier integrity marker"
    parts = matches[0].split(":")
    if len(parts) != 5 or not parts[2].isdigit():
        return False, "malformed verifier integrity marker"
    before, after = parts[3], parts[4]
    if not SHA256_RE.fullmatch(before) or not SHA256_RE.fullmatch(after):
        return False, "invalid protected-path digest"
    if before != after:
        return False, "protected test paths changed during verification"
    return True, None


def _normalize_statuses(raw: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise RebenchVerificationError("parser did not return a mapping")
    statuses: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise RebenchVerificationError("parser returned a malformed status entry")
        state = value.casefold()
        aliases = {"pass": "passed", "fail": "failed"}
        state = aliases.get(state, state)
        if state not in STATUS_VALUES:
            raise RebenchVerificationError(f"parser returned unknown status {value!r}")
        if key in statuses:
            raise RebenchVerificationError("parser returned a duplicate test id")
        statuses[key] = state
    return statuses


def _states(statuses: Mapping[str, str], ids: Sequence[str]) -> dict[str, str]:
    return {test_id: statuses.get(test_id, "missing") for test_id in ids}


def _bounded_receipt_error(message: str) -> str:
    """Escape controls and cap an error at 2,000 UTF-8 bytes without splitting a code point."""

    valid_unicode = message.encode("utf-8", errors="replace").decode("utf-8")
    sanitized = "".join(
        f"\\u{ord(char):04x}" if ord(char) < 32 or ord(char) == 127 else char
        for char in valid_unicode
    )
    if not sanitized:
        sanitized = "<empty error>"
    encoded = sanitized.encode("utf-8")
    if len(encoded) <= ERROR_MAX_UTF8_BYTES:
        return sanitized

    marker = ERROR_TRUNCATION_MARKER.encode("ascii")
    prefix = encoded[: ERROR_MAX_UTF8_BYTES - len(marker)]
    # Decode only complete code points.  Invalid source surrogates were
    # already replaced above, so ignoring here can drop only a split suffix.
    return prefix.decode("utf-8", errors="ignore") + ERROR_TRUNCATION_MARKER


def _exception_receipt_error(context: str, exc: Exception) -> str:
    try:
        detail = str(exc)
    except Exception:
        detail = "<exception text unavailable>"
    return _bounded_receipt_error(f"{context}: {type(exc).__name__}: {detail}")


def _valid_receipt_error(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return len(encoded) <= ERROR_MAX_UTF8_BYTES


def _score_run(
    *,
    result: DockerRunResult,
    parser: PinnedParser,
    material: VerifierMaterial,
    phase: str,
    repeat: int,
    marker_token: str,
) -> ScoredRun:
    error: str | None = None
    parser_ok = False
    statuses: dict[str, str] = {}
    integrity_ok, integrity_error = _integrity_marker(result.stderr, marker_token)
    if integrity_error:
        error = integrity_error
    if result.timed_out:
        error = error or "verifier timed out"
    elif result.output_truncated:
        error = error or "verifier output exceeded the cap"
    else:
        try:
            statuses = _normalize_statuses(parser(f"{result.stdout}\n{result.stderr}"))
            parser_ok = True
        except Exception as exc:
            error = error or _exception_receipt_error("parser failed", exc)

    f2p = _states(statuses, material.fail_to_pass)
    p2p = _states(statuses, material.pass_to_pass)
    if phase == "base":
        expected = (
            result.returncode == 1
            and all(state == "failed" for state in f2p.values())
            and all(state == "passed" for state in p2p.values())
        )
    else:
        expected = (
            result.returncode == 0
            and all(state == "passed" for state in f2p.values())
            and all(state == "passed" for state in p2p.values())
        )
    expectation_met = bool(expected and parser_ok and integrity_ok and error is None)
    if not expectation_met and error is None:
        error = f"{phase} result did not meet fail/pass and exit-status expectations"
    if error is not None:
        error = _bounded_receipt_error(error)
    return ScoredRun(
        phase=phase,
        repeat=repeat,
        expectation_met=expectation_met,
        returncode=result.returncode,
        timed_out=result.timed_out,
        output_truncated=result.output_truncated,
        parser_ok=parser_ok,
        integrity_ok=integrity_ok,
        fail_to_pass_states=f2p,
        pass_to_pass_states=p2p,
        stdout_sha256=result.stdout_sha256,
        stderr_sha256=result.stderr_sha256,
        stdout_head_sha256=result.stdout_head_sha256,
        stdout_tail_sha256=result.stdout_tail_sha256,
        stderr_head_sha256=result.stderr_head_sha256,
        stderr_tail_sha256=result.stderr_tail_sha256,
        stdout_captured_bytes=result.stdout_captured_bytes,
        stderr_captured_bytes=result.stderr_captured_bytes,
        command_sha256=result.command_sha256,
        error=error,
    )


def _failed_run(
    phase: str,
    repeat: int,
    error: str,
    material: VerifierMaterial,
) -> ScoredRun:
    return ScoredRun(
        phase=phase,
        repeat=repeat,
        expectation_met=False,
        returncode=None,
        timed_out=False,
        output_truncated=False,
        parser_ok=False,
        integrity_ok=False,
        fail_to_pass_states={test_id: "missing" for test_id in material.fail_to_pass},
        pass_to_pass_states={test_id: "missing" for test_id in material.pass_to_pass},
        stdout_sha256=_sha256(b""),
        stderr_sha256=_sha256(b""),
        stdout_head_sha256=_sha256(b""),
        stdout_tail_sha256=_sha256(b""),
        stderr_head_sha256=_sha256(b""),
        stderr_tail_sha256=_sha256(b""),
        stdout_captured_bytes=0,
        stderr_captured_bytes=0,
        command_sha256=_sha256(b""),
        error=_bounded_receipt_error(error),
    )


def qualify_task(
    task: QualificationTask,
    material: VerifierMaterial,
    *,
    parser: PinnedParser,
    backend: DockerBackend,
) -> dict[str, object]:
    """Run two base and two gold checks and return a hash-bound receipt.

    The caller is responsible for resolving ``parser`` from the vendored parser
    file whose SHA-256 is ``material.parser_sha256``.  This seam is explicit so
    an installed Python package cannot silently replace the pinned parser.
    """

    _validate_task(task)
    _validate_material(material)
    if not isinstance(parser, PinnedParser):
        raise RebenchVerificationError("parser must be loaded from hash-bound source bytes")
    if parser.name != material.parser_name or parser.source_sha256 != material.parser_sha256:
        raise RebenchVerificationError("executed parser does not match verifier material")
    protected = protected_paths(material.gold_patch, material.test_patch)
    runs: list[ScoredRun] = []
    for phase, patch in (("base", ""), ("gold", material.gold_patch)):
        for repeat in (1, 2):
            marker_token = uuid.uuid4().hex
            payload = build_verifier_payload(
                product_patch=patch,
                material=material,
                protected=protected,
                marker_token=marker_token,
            )
            script = _runner_script(marker_token)
            try:
                result = backend.run_verifier(
                    image=task.image_reference,
                    workdir=task.workdir,
                    command=("/bin/bash", "-c", script),
                    stdin=payload,
                    timeout_s=task.verify_timeout_s,
                )
                runs.append(
                    _score_run(
                        result=result,
                        parser=parser,
                        material=material,
                        phase=phase,
                        repeat=repeat,
                        marker_token=marker_token,
                    )
                )
            except DockerIsolationError as exc:
                runs.append(
                    _failed_run(
                        phase,
                        repeat,
                        _exception_receipt_error("Docker isolation failed", exc),
                        material,
                    )
                )

    base_runs = [run for run in runs if run.phase == "base"]
    gold_runs = [run for run in runs if run.phase == "gold"]
    qualified = (
        len(base_runs) == 2
        and len(gold_runs) == 2
        and all(run.expectation_met for run in runs)
    )
    receipt: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "instance_id": task.instance_id,
        "image_reference": task.image_reference,
        "image_digest": task.image_digest,
        "workdir": task.workdir,
        "verify_timeout_s": task.verify_timeout_s,
        "parser_name": material.parser_name,
        "parser_sha256": material.parser_sha256,
        "gold_patch_sha256": _sha256(material.gold_patch),
        "test_patch_sha256": _sha256(material.test_patch),
        "test_command_sha256": _sha256(material.test_command),
        "base_fail_repeats": sum(run.expectation_met for run in base_runs),
        "gold_pass_repeats": sum(run.expectation_met for run in gold_runs),
        "qualified": qualified,
        "runs": [asdict(run) for run in runs],
    }
    receipt["receipt_sha256"] = _sha256(dump_canonical_json(receipt))
    return receipt


def verify_receipt(receipt: Mapping[str, object]) -> bool:
    """Verify receipt bytes *and* every claimed qualification semantic."""

    receipt_keys = {
        "schema_version",
        "instance_id",
        "image_reference",
        "image_digest",
        "workdir",
        "verify_timeout_s",
        "parser_name",
        "parser_sha256",
        "gold_patch_sha256",
        "test_patch_sha256",
        "test_command_sha256",
        "base_fail_repeats",
        "gold_pass_repeats",
        "qualified",
        "runs",
        "receipt_sha256",
    }
    run_keys = {
        "phase",
        "repeat",
        "expectation_met",
        "returncode",
        "timed_out",
        "output_truncated",
        "parser_ok",
        "integrity_ok",
        "fail_to_pass_states",
        "pass_to_pass_states",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_head_sha256",
        "stdout_tail_sha256",
        "stderr_head_sha256",
        "stderr_tail_sha256",
        "stdout_captured_bytes",
        "stderr_captured_bytes",
        "command_sha256",
        "error",
    }

    if not isinstance(receipt, Mapping) or set(receipt) != receipt_keys:
        return False
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        return False
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
        return False
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    try:
        if _sha256(dump_canonical_json(body)) != claimed:
            return False
    except (TypeError, ValueError):
        return False

    instance_id = receipt.get("instance_id")
    image_reference = receipt.get("image_reference")
    image_digest = receipt.get("image_digest")
    workdir = receipt.get("workdir")
    if (
        not isinstance(instance_id, str)
        or not instance_id
        or set(instance_id) & {"\0", "\r", "\n"}
        or not isinstance(image_reference, str)
        or not IMAGE_RE.fullmatch(image_reference)
        or not isinstance(image_digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest)
        or not image_reference.endswith(f"@{image_digest}")
        or not isinstance(workdir, str)
        or not workdir.startswith("/")
        or workdir == "/"
        or ".." in PurePosixPath(workdir).parts
        or receipt.get("verify_timeout_s") != 900
        or receipt.get("parser_name") not in SUPPORTED_LOG_PARSERS
    ):
        return False
    for name in (
        "parser_sha256",
        "gold_patch_sha256",
        "test_patch_sha256",
        "test_command_sha256",
    ):
        value = receipt.get(name)
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            return False
    for name in ("base_fail_repeats", "gold_pass_repeats"):
        value = receipt.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 2):
            return False
    if not isinstance(receipt.get("qualified"), bool):
        return False

    runs = receipt.get("runs")
    if not isinstance(runs, list) or len(runs) != 4:
        return False
    expected_order = [("base", 1), ("base", 2), ("gold", 1), ("gold", 2)]
    f2p_keys: set[str] | None = None
    p2p_keys: set[str] | None = None
    met_values: list[bool] = []
    for raw, (phase, repeat) in zip(runs, expected_order):
        if not isinstance(raw, Mapping) or set(raw) != run_keys:
            return False
        if raw.get("phase") != phase or raw.get("repeat") != repeat:
            return False
        for name in ("expectation_met", "timed_out", "output_truncated", "parser_ok", "integrity_ok"):
            if not isinstance(raw.get(name), bool):
                return False
        returncode = raw.get("returncode")
        if returncode is not None and (isinstance(returncode, bool) or not isinstance(returncode, int)):
            return False
        error = raw.get("error")
        if error is not None and not _valid_receipt_error(error):
            return False
        for name in (
            "stdout_sha256",
            "stderr_sha256",
            "stdout_head_sha256",
            "stdout_tail_sha256",
            "stderr_head_sha256",
            "stderr_tail_sha256",
            "command_sha256",
        ):
            value = raw.get(name)
            if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                return False
        for name in ("stdout_captured_bytes", "stderr_captured_bytes"):
            value = raw.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 20_000_000):
                return False

        status_maps: list[dict[str, str]] = []
        for name in ("fail_to_pass_states", "pass_to_pass_states"):
            mapping = raw.get(name)
            if not isinstance(mapping, Mapping):
                return False
            normalized: dict[str, str] = {}
            for test_id, state in mapping.items():
                if (
                    not isinstance(test_id, str)
                    or not test_id
                    or set(test_id) & {"\0", "\r", "\n"}
                    or not isinstance(state, str)
                    or state not in STATUS_VALUES | {"missing"}
                ):
                    return False
                normalized[test_id] = state
            status_maps.append(normalized)
        f2p, p2p = status_maps
        if not f2p:
            return False
        if f2p_keys is None:
            f2p_keys, p2p_keys = set(f2p), set(p2p)
        elif set(f2p) != f2p_keys or set(p2p) != p2p_keys:
            return False

        common_ok = (
            raw["parser_ok"] is True
            and raw["integrity_ok"] is True
            and raw["timed_out"] is False
            and raw["output_truncated"] is False
            and error is None
        )
        if phase == "base":
            semantic_met = (
                common_ok
                and returncode == 1
                and all(state == "failed" for state in f2p.values())
                and all(state == "passed" for state in p2p.values())
            )
        else:
            semantic_met = (
                common_ok
                and returncode == 0
                and all(state == "passed" for state in f2p.values())
                and all(state == "passed" for state in p2p.values())
            )
        if raw["expectation_met"] is not semantic_met:
            return False
        if not semantic_met and error is None:
            return False
        met_values.append(semantic_met)

    base_count = sum(met_values[:2])
    gold_count = sum(met_values[2:])
    qualified = all(met_values) and base_count == 2 and gold_count == 2
    return bool(
        receipt["base_fail_repeats"] == base_count
        and receipt["gold_pass_repeats"] == gold_count
        and receipt["qualified"] is qualified
    )
