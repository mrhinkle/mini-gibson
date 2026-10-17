"""Qualification verifier for pinned SWE-rebench task images.

This module handles hidden verifier material on the trusted host.  It is not an
agent entrypoint.  Qualification requires two independent base failures and two
independent gold successes, each in a fresh container.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import shlex
import sys
import tarfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

from .cohort import SUPPORTED_LOG_PARSERS, dump_canonical_json
from .docker_backend import DockerBackend, DockerIsolationError, DockerRunResult, IMAGE_RE


RECEIPT_SCHEMA = "mini-gibson-rebench-qualification/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STATUS_VALUES = {"passed", "failed", "error", "skipped"}
MARKER_PREFIX = "__MINI_GIBSON_VERIFIER_V1__"


class RebenchVerificationError(ValueError):
    """Verifier input is unsafe or internally inconsistent."""


Parser = Callable[[str], Mapping[str, str]]


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
    command_sha256: str
    error: str | None


def load_pinned_parser(
    parser_path: str | Path,
    parser_name: str,
    expected_sha256: str,
) -> Parser:
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
    source = path.read_bytes()
    if _sha256(source) != expected_sha256:
        raise RebenchVerificationError("pinned parser bytes do not match parser_sha256")
    module_name = f"_mini_gibson_rebench_parser_{expected_sha256[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RebenchVerificationError("could not create the pinned parser module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RebenchVerificationError(f"could not load pinned parser: {type(exc).__name__}: {exc}") from exc
    finally:
        sys.modules.pop(module_name, None)
    parser = getattr(module, parser_name, None)
    if not callable(parser):
        raise RebenchVerificationError(f"pinned parser does not define callable {parser_name}")
    return parser


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


def _safe_patch_path(raw: str) -> str | None:
    if raw == "/dev/null":
        return None
    if raw.startswith(("a/", "b/")):
        raw = raw[2:]
    path = PurePosixPath(raw)
    if not raw or raw.startswith("/") or any(part in {"", ".", ".."} for part in path.parts):
        raise RebenchVerificationError(f"patch contains unsafe path {raw!r}")
    if path.parts[0] == ".git" or any(char in raw for char in "\0\r\n"):
        raise RebenchVerificationError(f"patch contains forbidden path {raw!r}")
    return raw


def patch_paths(patch: str) -> set[str]:
    """Return safe paths from a git patch, rejecting ambiguous diff headers."""

    paths: set[str] = set()
    headers = 0
    for line in patch.splitlines():
        if not line.startswith("diff --git "):
            continue
        headers += 1
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            raise RebenchVerificationError("patch contains malformed diff header") from exc
        if len(parts) != 4 or parts[:2] != ["diff", "--git"]:
            raise RebenchVerificationError("patch contains malformed diff header")
        old_path = _safe_patch_path(parts[2])
        new_path = _safe_patch_path(parts[3])
        if old_path is not None:
            paths.add(old_path)
        if new_path is not None:
            paths.add(new_path)
    if patch.strip() and headers == 0:
        raise RebenchVerificationError("patch has no git diff headers")
    return paths


def _looks_like_test_path(path: str) -> bool:
    folded = path.casefold()
    parts = PurePosixPath(folded).parts
    name = parts[-1]
    return (
        any(part in {"test", "tests", "__tests__", "spec", "specs"} for part in parts[:-1])
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
test -z "$(git status --porcelain=v1 --untracked-files=no)" || exit 84
if test -s "$stage/product.patch"; then
  git apply --check --whitespace=nowarn "$stage/product.patch" || exit 85
  git apply --whitespace=nowarn "$stage/product.patch" || exit 86
fi
git apply --check --whitespace=nowarn "$stage/test.patch" || exit 87
git apply --whitespace=nowarn "$stage/test.patch" || exit 88

{{ git ls-files; cat "$stage/protected-paths"; }} | awk '
  /(^|\/)(tests?|__tests__|specs?)(\/|$)/ ||
  /(^|\/)(test_|spec_)[^\/]*$/ ||
  /\.(test|spec)\.[^\/]*$/ ||
  /_(test|spec)\.[^\/]*$/ {{ print }}
' | LC_ALL=C sort -u > "$stage/all-protected"

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


def _score_run(
    *,
    result: DockerRunResult,
    parser: Parser,
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
            error = error or f"parser failed: {type(exc).__name__}: {exc}"

    f2p = _states(statuses, material.fail_to_pass)
    p2p = _states(statuses, material.pass_to_pass)
    if phase == "base":
        expected = (
            result.returncode not in {None, 0}
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
        stdout_sha256=_sha256(result.stdout),
        stderr_sha256=_sha256(result.stderr),
        command_sha256=result.command_sha256,
        error=error,
    )


def _failed_run(phase: str, repeat: int, error: str) -> ScoredRun:
    return ScoredRun(
        phase=phase,
        repeat=repeat,
        expectation_met=False,
        returncode=None,
        timed_out=False,
        output_truncated=False,
        parser_ok=False,
        integrity_ok=False,
        fail_to_pass_states={},
        pass_to_pass_states={},
        stdout_sha256=_sha256(b""),
        stderr_sha256=_sha256(b""),
        command_sha256=_sha256(b""),
        error=error,
    )


def qualify_task(
    task: QualificationTask,
    material: VerifierMaterial,
    *,
    parser: Parser,
    backend: DockerBackend,
) -> dict[str, object]:
    """Run two base and two gold checks and return a hash-bound receipt.

    The caller is responsible for resolving ``parser`` from the vendored parser
    file whose SHA-256 is ``material.parser_sha256``.  This seam is explicit so
    an installed Python package cannot silently replace the pinned parser.
    """

    _validate_task(task)
    _validate_material(material)
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
                runs.append(_failed_run(phase, repeat, f"Docker isolation failed: {exc}"))

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
    """Verify receipt structure, run count, outcomes, and self hash."""

    if not isinstance(receipt, Mapping) or receipt.get("schema_version") != RECEIPT_SCHEMA:
        return False
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
        return False
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if _sha256(dump_canonical_json(body)) != claimed:
        return False
    runs = receipt.get("runs")
    if not isinstance(runs, list) or len(runs) != 4:
        return False
    expected_order = [("base", 1), ("base", 2), ("gold", 1), ("gold", 2)]
    actual_order = [(run.get("phase"), run.get("repeat")) for run in runs if isinstance(run, dict)]
    if actual_order != expected_order:
        return False
    all_met = all(run.get("expectation_met") is True for run in runs if isinstance(run, dict))
    return bool(
        receipt.get("qualified") is all_met
        and receipt.get("base_fail_repeats") == sum(
            run.get("expectation_met") is True for run in runs[:2]
        )
        and receipt.get("gold_pass_repeats") == sum(
            run.get("expectation_met") is True for run in runs[2:]
        )
    )
