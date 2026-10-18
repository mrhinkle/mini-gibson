from __future__ import annotations

import copy
import hashlib
import io
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from evaluation.docker_backend import DockerIsolationError, DockerRunResult
from evaluation.cohort import dump_canonical_json
from evaluation.verify_rebench import (
    ERROR_MAX_UTF8_BYTES,
    ERROR_TRUNCATION_MARKER,
    MARKER_PREFIX,
    QualificationTask,
    RebenchVerificationError,
    VerifierMaterial,
    _runner_script,
    build_verifier_payload,
    load_pinned_parser,
    load_pinned_parser_bytes,
    patch_paths,
    protected_paths,
    qualify_task,
    verify_receipt,
)


DIGEST = "sha256:" + "b" * 64
PARSER_SOURCE = b"""def parse_log_pytest(output):
    state = "passed" if "GOLD" in output else "failed"
    return {
        "tests/test_math.py::test_fix": state,
        "tests/test_math.py::test_existing": "passed",
    }
"""
PARSER_SHA256 = hashlib.sha256(PARSER_SOURCE).hexdigest()
PINNED_PARSER = load_pinned_parser_bytes(PARSER_SOURCE, "parse_log_pytest", PARSER_SHA256)


def _patch(path: str, before: str = "old", after: str = "new") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        f"-{before}\n"
        f"+{after}\n"
    )


def _move_patch(kind: str, old: str, new: str, *, quoted: bool = False) -> str:
    assert kind in {"rename", "copy"}
    old_header = f'"a/{old}"' if quoted else f"a/{old}"
    new_header = f'"b/{new}"' if quoted else f"b/{new}"
    old_meta = f'"{old}"' if quoted else old
    new_meta = f'"{new}"' if quoted else new
    return (
        f"diff --git {old_header} {new_header}\n"
        "similarity index 100%\n"
        f"{kind} from {old_meta}\n"
        f"{kind} to {new_meta}\n"
    )


def _create_patch(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1 @@\n"
        "+created\n"
    )


def _delete_patch(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "deleted file mode 100644\n"
        f"--- a/{path}\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-old\n"
    )


def task() -> QualificationTask:
    return QualificationTask(
        instance_id="owner__repo-123",
        image_reference=f"registry.example/rebench/task@{DIGEST}",
        image_digest=DIGEST,
        workdir="/testbed",
    )


def material(**changes) -> VerifierMaterial:
    values = {
        "gold_patch": _patch("src/math.py"),
        "test_patch": _patch("tests/test_math.py", "weak", "strict"),
        "fail_to_pass": ("tests/test_math.py::test_fix",),
        "pass_to_pass": ("tests/test_math.py::test_existing",),
        "test_command": "pytest -q -rA",
        "parser_name": "parse_log_pytest",
        "parser_sha256": PARSER_SHA256,
    }
    values.update(changes)
    return VerifierMaterial(**values)


class FakeBackend:
    def __init__(self, overrides=None, docker_error_at: int | None = None) -> None:
        self.calls = []
        self.overrides = overrides or {}
        self.docker_error_at = docker_error_at

    def run_verifier(self, *, image, workdir, command, stdin, timeout_s):
        index = len(self.calls)
        self.calls.append((image, workdir, command, stdin, timeout_s))
        if self.docker_error_at == index:
            raise DockerIsolationError("daemon unavailable")
        with tarfile.open(fileobj=io.BytesIO(stdin), mode="r:") as archive:
            product = archive.extractfile("product.patch").read().decode()
            names = archive.getnames()
        assert names == ["product.patch", "test.patch", "test-command", "protected-paths"]
        phase = "gold" if product else "base"
        token = re.search(rf"{MARKER_PREFIX}:([0-9a-f]{{32}}):", command[2]).group(1)
        digest = hashlib.sha256(b"protected").hexdigest()
        values = {
            "returncode": 0 if phase == "gold" else 1,
            "stdout": phase.upper(),
            "stderr": f"{MARKER_PREFIX}:{token}:{0 if phase == 'gold' else 1}:{digest}:{digest}\n",
            "timed_out": False,
            "output_truncated": False,
        }
        values.update(self.overrides.get(index, {}))
        return DockerRunResult(
            container_name=f"mini-gibson-verifier-{index:012x}",
            command_sha256=hashlib.sha256(str(index).encode()).hexdigest(),
            **values,
        )


def test_qualification_requires_two_fresh_base_fails_and_gold_passes() -> None:
    backend = FakeBackend()
    receipt = qualify_task(task(), material(), parser=PINNED_PARSER, backend=backend)

    assert receipt["qualified"] is True
    assert receipt["base_fail_repeats"] == 2
    assert receipt["gold_pass_repeats"] == 2
    assert [(run["phase"], run["repeat"]) for run in receipt["runs"]] == [
        ("base", 1),
        ("base", 2),
        ("gold", 1),
        ("gold", 2),
    ]
    assert len(backend.calls) == 4
    assert all(call[0] == task().image_reference for call in backend.calls)
    assert all(call[4] == 900 for call in backend.calls)
    assert verify_receipt(receipt) is True
    rendered = str(receipt)
    assert "src/math.py" not in rendered
    assert "tests/test_math.py::test_fix" in rendered
    assert "-old" not in rendered and "+new" not in rendered


def test_qualification_preserves_multiline_test_identifiers() -> None:
    test_id = "Compiles: fun test() {\n    println()\n} (ExampleSpec)"
    source = (
        "def parse_log_pytest(output):\n"
        f"    return {{{test_id!r}: 'passed' if 'GOLD' in output else 'failed'}}\n"
    ).encode()
    digest = hashlib.sha256(source).hexdigest()
    parser = load_pinned_parser_bytes(source, "parse_log_pytest", digest)

    receipt = qualify_task(
        task(),
        material(
            fail_to_pass=(test_id,),
            pass_to_pass=(),
            parser_sha256=digest,
        ),
        parser=parser,
        backend=FakeBackend(),
    )

    assert receipt["qualified"] is True
    assert all(test_id in run["fail_to_pass_states"] for run in receipt["runs"])
    assert verify_receipt(receipt) is True


def test_qualification_rejects_unsafe_controls_in_test_identifier() -> None:
    for bad in ("", "bad\0selector", "bad\rselector"):
        with pytest.raises(RebenchVerificationError, match="without NUL"):
            qualify_task(
                task(),
                material(fail_to_pass=(bad,)),
                parser=PINNED_PARSER,
                backend=FakeBackend(),
            )


@pytest.mark.parametrize(
    "overrides",
    [
        {2: {"returncode": 4}},
        {3: {"timed_out": True, "returncode": -9}},
        {2: {"output_truncated": True}},
        {0: {"returncode": 0}},
        {2: {"stderr": "no integrity marker"}},
    ],
)
def test_nonzero_timeout_truncation_and_integrity_fail_closed(overrides) -> None:
    receipt = qualify_task(task(), material(), parser=PINNED_PARSER, backend=FakeBackend(overrides))
    assert receipt["qualified"] is False
    assert verify_receipt(receipt) is True
    assert any(not run["expectation_met"] for run in receipt["runs"])


def test_parser_failure_or_missing_required_status_fails_closed() -> None:
    exploding_source = b"def parse_log_pytest(_output):\n    raise RuntimeError('bad parser output')\n"
    exploding_hash = hashlib.sha256(exploding_source).hexdigest()
    exploding = load_pinned_parser_bytes(exploding_source, "parse_log_pytest", exploding_hash)

    failed = qualify_task(
        task(),
        material(parser_sha256=exploding_hash),
        parser=exploding,
        backend=FakeBackend(),
    )
    assert failed["qualified"] is False
    assert all(run["parser_ok"] is False for run in failed["runs"])

    missing_source = b"def parse_log_pytest(_output):\n    return {}\n"
    missing_hash = hashlib.sha256(missing_source).hexdigest()
    missing_parser = load_pinned_parser_bytes(missing_source, "parse_log_pytest", missing_hash)
    missing = qualify_task(
        task(),
        material(parser_sha256=missing_hash),
        parser=missing_parser,
        backend=FakeBackend(),
    )
    assert missing["qualified"] is False
    assert all("missing" in run["fail_to_pass_states"].values() for run in missing["runs"])


def _receipt_from_parser_source(source: bytes) -> dict[str, object]:
    digest = hashlib.sha256(source).hexdigest()
    parser = load_pinned_parser_bytes(source, "parse_log_pytest", digest)
    return qualify_task(
        task(),
        material(parser_sha256=digest),
        parser=parser,
        backend=FakeBackend(),
    )


def test_long_parser_exception_is_bounded_and_self_verifies() -> None:
    message = "parser detail\n" + "x" * (ERROR_MAX_UTF8_BYTES * 2)
    source = f"def parse_log_pytest(_output):\n    raise RuntimeError({message!r})\n".encode()
    receipt = _receipt_from_parser_source(source)

    assert receipt["qualified"] is False
    for run in receipt["runs"]:
        error = run["error"]
        assert error.startswith("parser failed: RuntimeError: parser detail\\u000a")
        assert error.endswith(ERROR_TRUNCATION_MARKER)
        assert len(error.encode("utf-8")) <= ERROR_MAX_UTF8_BYTES
    assert verify_receipt(receipt) is True


def test_long_unknown_status_truncates_on_a_unicode_boundary() -> None:
    unknown = "unknown-" + "💥" * ERROR_MAX_UTF8_BYTES
    source = (
        "def parse_log_pytest(_output):\n"
        f"    return {{'tests/test_math.py::test_fix': {unknown!r}}}\n"
    ).encode()
    receipt = _receipt_from_parser_source(source)

    for run in receipt["runs"]:
        error = run["error"]
        assert error.startswith("parser failed: RebenchVerificationError: parser returned unknown status")
        assert error.endswith(ERROR_TRUNCATION_MARKER)
        assert "�" not in error
        assert len(error.encode("utf-8")) <= ERROR_MAX_UTF8_BYTES
    assert verify_receipt(receipt) is True


def test_error_at_exact_utf8_limit_is_not_truncated() -> None:
    prefix = "parser failed: RuntimeError: "
    message = "e" * (ERROR_MAX_UTF8_BYTES - len(prefix.encode("utf-8")))
    source = f"def parse_log_pytest(_output):\n    raise RuntimeError({message!r})\n".encode()
    receipt = _receipt_from_parser_source(source)

    for run in receipt["runs"]:
        error = run["error"]
        assert len(error.encode("utf-8")) == ERROR_MAX_UTF8_BYTES
        assert not error.endswith(ERROR_TRUNCATION_MARKER)
    assert verify_receipt(receipt) is True


def test_tampered_over_limit_error_rejects_even_with_recomputed_hash() -> None:
    source = b"def parse_log_pytest(_output):\n    raise RuntimeError('bounded')\n"
    receipt = _receipt_from_parser_source(source)
    receipt["runs"][0]["error"] = "x" * (ERROR_MAX_UTF8_BYTES + 1)
    _rehash_receipt(receipt)
    assert verify_receipt(receipt) is False


def test_long_docker_error_uses_the_same_receipt_bound() -> None:
    class LongDockerFailure(FakeBackend):
        def run_verifier(self, **_kwargs):
            raise DockerIsolationError("daemon\n" + "💥" * ERROR_MAX_UTF8_BYTES)

    receipt = qualify_task(task(), material(), parser=PINNED_PARSER, backend=LongDockerFailure())
    for run in receipt["runs"]:
        error = run["error"]
        assert error.startswith("Docker isolation failed: DockerIsolationError: daemon\\u000a")
        assert error.endswith(ERROR_TRUNCATION_MARKER)
        assert len(error.encode("utf-8")) <= ERROR_MAX_UTF8_BYTES
    assert verify_receipt(receipt) is True


def test_docker_failure_is_recorded_and_does_not_skip_other_repeats() -> None:
    backend = FakeBackend(docker_error_at=1)
    receipt = qualify_task(task(), material(), parser=PINNED_PARSER, backend=backend)
    assert receipt["qualified"] is False
    assert len(backend.calls) == 4
    assert "Docker isolation failed" in receipt["runs"][1]["error"]
    assert verify_receipt(receipt) is True


def test_product_patch_cannot_touch_hidden_or_conventional_test_paths() -> None:
    with pytest.raises(RebenchVerificationError, match="protected test paths"):
        qualify_task(
            task(),
            material(gold_patch=_patch("tests/test_math.py", "wrong", "cheat")),
            parser=PINNED_PARSER,
            backend=FakeBackend(),
        )
    for patch in (
        _move_patch("rename", "tests/test_old.py", "tests/test_new.py"),
        _move_patch("copy", "src/math.py", "tests/test_math_copy.py"),
        _move_patch("rename", "tests/test old.py", "tests/test new.py", quoted=True),
    ):
        with pytest.raises(RebenchVerificationError, match="protected test paths"):
            qualify_task(
                task(),
                material(gold_patch=patch),
                parser=PINNED_PARSER,
                backend=FakeBackend(),
            )
    with pytest.raises(RebenchVerificationError, match="protected test paths"):
        qualify_task(
            task(),
            material(gold_patch=_patch("spec/math.spec.ts")),
            parser=PINNED_PARSER,
            backend=FakeBackend(),
        )


def test_patch_paths_reject_traversal_malformed_and_git_metadata() -> None:
    assert patch_paths(_patch("src/file.py")) == {"src/file.py"}
    for bad in (
        _patch("../escape"),
        _patch(".git/config"),
        "this is not a patch\n",
        'diff --git "a/broken b/broken\n',
    ):
        with pytest.raises(RebenchVerificationError):
            patch_paths(bad)


def test_patch_paths_reject_unsafe_rename_and_copy_metadata() -> None:
    attacks = (
        (
            "diff --git a/src/ok.py b/src/new.py\n"
            "rename from .git/config\n"
            "rename to src/new.py\n"
        ),
        (
            "diff --git a/src/ok.py b/src/new.py\n"
            "copy from ../outside.py\n"
            "copy to src/new.py\n"
        ),
        (
            'diff --git "a/src/ok.py" "b/src/new.py"\n'
            'rename from "src/../../.git/config"\n'
            'rename to "src/new.py"\n'
        ),
    )
    for attack in attacks:
        with pytest.raises(RebenchVerificationError, match="forbidden|unsafe|noncanonical"):
            patch_paths(attack)


def test_patch_paths_accept_quoted_spaces_and_reconcile_all_headers() -> None:
    renamed = _move_patch("rename", "src/old name.py", "src/new name.py", quoted=True)
    assert patch_paths(renamed) == {"src/old name.py", "src/new name.py"}

    changed = (
        'diff --git "a/src/file name.py" "b/src/file name.py"\n'
        '--- "a/src/file name.py"\n'
        '+++ "b/src/file name.py"\n'
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    assert patch_paths(changed) == {"src/file name.py"}

    assert patch_paths(_create_patch("src/new.py")) == {"src/new.py"}
    assert patch_paths(_delete_patch("src/old.py")) == {"src/old.py"}


@pytest.mark.parametrize(
    "bad_patch",
    [
        "diff --git x/conftest.py b/conftest.py\n",
        "diff --git a/conftest.py c/conftest.py\n",
        "diff --git conftest.py b/conftest.py\n",
        "diff --git b/conftest.py a/conftest.py\n",
        "diff --git a/old b/name.py b/new.py\n",
        'diff --git "x/conftest.py" "b/conftest.py"\n',
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- x/src/file.py\n"
            "+++ b/src/file.py\n"
        ),
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- a/src/file.py\n"
            "+++ c/src/file.py\n"
        ),
    ],
)
def test_diff_and_file_headers_require_exact_a_b_prefixes(bad_patch: str) -> None:
    with pytest.raises(RebenchVerificationError, match="canonical|malformed|ambiguous"):
        patch_paths(bad_patch)


def test_valid_a_b_rename_copy_and_test_config_overlap() -> None:
    assert patch_paths(_move_patch("rename", "src/old.py", "src/new.py")) == {
        "src/old.py",
        "src/new.py",
    }
    assert patch_paths(_move_patch("copy", "src/source.py", "src/copy.py")) == {
        "src/source.py",
        "src/copy.py",
    }
    for path in ("conftest.py", "pytest.ini", "tox.ini"):
        with pytest.raises(RebenchVerificationError, match="protected test paths"):
            protected_paths(_patch(path), _patch(path))


def _git(root: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _init_runner_repo(root: Path, files: dict[str, str]) -> None:
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")


def _run_local_runner(
    root: Path,
    verifier_material: VerifierMaterial,
    protected: tuple[str, ...],
) -> subprocess.CompletedProcess[bytes]:
    token = "f" * 32
    payload = build_verifier_payload(
        product_patch="",
        material=verifier_material,
        protected=protected,
        marker_token=token,
    )
    return subprocess.run(
        ["/bin/bash", "-c", _runner_script(token)],
        cwd=root,
        input=payload,
        capture_output=True,
        check=False,
    )


def test_runner_rejects_git_status_failure_even_with_empty_stdout(tmp_path: Path) -> None:
    root = tmp_path / "corrupt-status"
    _init_runner_repo(root, {"src/value.py": "old\n"})
    verifier_material = material(
        test_patch=_patch("src/value.py"),
        test_command="true",
    )
    (root / ".git/index").write_bytes(b"not a git index")

    result = _run_local_runner(root, verifier_material, ("src/value.py",))

    assert result.returncode == 84
    assert result.stdout == b""
    assert MARKER_PREFIX.encode() not in result.stderr


@pytest.mark.parametrize(
    "mutated_path",
    ["src/pkg/checks.py", "conftest.py", "pytest.ini", "tox.ini"],
)
def test_runner_hashes_every_sealed_helper_and_tracked_root_config(
    tmp_path: Path,
    mutated_path: str,
) -> None:
    root = tmp_path / mutated_path.replace("/", "-")
    files = {"src/pkg/checks.py": "old\n"}
    files.setdefault(mutated_path, "stable\n")
    _init_runner_repo(root, files)
    test_patch = _patch("src/pkg/checks.py")
    verifier_material = material(
        test_patch=test_patch,
        test_command=f"printf 'tampered\\n' > {mutated_path}",
    )

    result = _run_local_runner(root, verifier_material, ("src/pkg/checks.py",))

    assert result.returncode == 97
    marker = re.search(
        rf"{MARKER_PREFIX}:{'f' * 32}:0:([0-9a-f]{{64}}):([0-9a-f]{{64}})",
        result.stderr.decode(),
    )
    assert marker is not None
    assert marker.group(1) != marker.group(2)


@pytest.mark.parametrize(
    "unsafe_path",
    ["", "/absolute", "../escape", "src//checks.py", "src/../checks.py", "src\\checks.py", "src/\tchecks.py"],
)
def test_runner_rejects_noncanonical_sealed_protected_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    root = tmp_path / "unsafe-protected"
    _init_runner_repo(root, {"src/value.py": "old\n"})
    verifier_material = material(
        test_patch=_patch("src/value.py"),
        test_command="true",
    )

    result = _run_local_runner(root, verifier_material, (unsafe_path,))

    assert result.returncode == 94
    assert MARKER_PREFIX.encode() not in result.stderr


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def test_patch_parser_matches_git_apply_p1_targets(tmp_path: Path) -> None:
    """Every path mutated by real git apply -p1 is present in patch_paths."""

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    for name in (
        "modify.txt",
        "delete.txt",
        "rename-old.txt",
        "copy-source.txt",
        "space file.txt",
    ):
        (root / name).write_text(f"base {name}\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")

    def modify() -> None:
        (root / "modify.txt").write_text("modified\n")

    def create() -> None:
        (root / "created.txt").write_text("created\n")
        _git(root, "add", "-N", "created.txt")

    def delete() -> None:
        (root / "delete.txt").unlink()

    def rename() -> None:
        _git(root, "mv", "rename-old.txt", "rename-new.txt")

    def copy() -> None:
        shutil.copyfile(root / "copy-source.txt", root / "copy-dest.txt")
        _git(root, "add", "-N", "copy-dest.txt")

    def quoted_space() -> None:
        (root / "space file.txt").write_text("space modified\n")

    cases = (
        ("modify", modify, ("diff", "--binary", "--no-ext-diff")),
        ("create", create, ("diff", "--binary", "--no-ext-diff")),
        ("delete", delete, ("diff", "--binary", "--no-ext-diff")),
        ("rename", rename, ("diff", "--binary", "--no-ext-diff", "-M")),
        (
            "copy",
            copy,
            ("diff", "--binary", "--no-ext-diff", "-C", "--find-copies-harder"),
        ),
        ("quoted-space", quoted_space, ("diff", "--binary", "--no-ext-diff")),
    )
    for label, mutate, diff_args in cases:
        _git(root, "reset", "--hard", "-q", "HEAD")
        _git(root, "clean", "-fdq")
        mutate()
        patch = _git(root, *diff_args, "HEAD")
        assert patch, label
        if label == "rename":
            assert "rename from rename-old.txt" in patch
        if label == "copy":
            assert "copy from copy-source.txt" in patch
        if label == "quoted-space":
            assert "--- a/space file.txt\t" in patch
        parsed = patch_paths(patch)

        _git(root, "reset", "--hard", "-q", "HEAD")
        _git(root, "clean", "-fdq")
        before = _snapshot(root)
        _git(root, "apply", "-p1", "-", input_text=patch)
        after = _snapshot(root)
        mutated = {
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        }
        assert mutated, label
        assert mutated <= parsed, (label, mutated, parsed)


def test_hunk_payload_header_lookalikes_are_counted_not_reparsed() -> None:
    hunk = (
        "diff --git a/src/comments.py b/src/comments.py\n"
        "--- a/src/comments.py\n"
        "+++ b/src/comments.py\n"
        "@@ -1,3 +1,3 @@\n"
        "--- old comment\n"
        "+++ content\n"
        "--- ../../.git/config\n"
        "+++ ./conftest.py\n"
        " rename from ../still-hunk-content\n"
    )
    assert patch_paths(hunk) == {"src/comments.py"}


def test_headerless_second_protected_file_is_rejected_even_when_git_applies_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "headerless"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "src/app.py").write_text("value = 1\n")
    (root / "tests/test_app.py").write_text("expected = 1\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")

    (root / "src/app.py").write_text("value = 2\n")
    (root / "tests/test_app.py").write_text("expected = 2\n")
    full_patch = _git(root, "diff", "--binary", "--no-ext-diff", "HEAD")
    second_header = full_patch.index("diff --git a/tests/test_app.py b/tests/test_app.py\n")
    second_file_headers = full_patch.index("--- a/tests/test_app.py", second_header)
    attack = full_patch[:second_header] + full_patch[second_file_headers:]

    _git(root, "reset", "--hard", "-q", "HEAD")
    _git(root, "apply", "-p1", "-", input_text=attack)
    assert (root / "src/app.py").read_text() == "value = 2\n"
    assert (root / "tests/test_app.py").read_text() == "expected = 2\n"
    with pytest.raises(RebenchVerificationError, match="header-only second file"):
        patch_paths(attack)


def test_multiple_hunks_and_no_newline_markers_are_bounded(tmp_path: Path) -> None:
    root = tmp_path / "multi-hunk"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    original = [f"line {index}\n" for index in range(1, 31)]
    (root / "module.py").write_text("".join(original))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    changed = original.copy()
    changed[1] = "line two changed\n"
    changed[27] = "line twenty-eight changed\n"
    (root / "module.py").write_text("".join(changed))
    patch = _git(root, "diff", "--binary", "--no-ext-diff", "--unified=1", "HEAD")
    assert sum(line.startswith("@@") for line in patch.splitlines()) == 2
    assert patch_paths(patch) == {"module.py"}

    _git(root, "reset", "--hard", "-q", "HEAD")
    _git(root, "apply", "-p1", "-", input_text=patch)
    assert (root / "module.py").read_text() == "".join(changed)

    no_newline = (
        "diff --git a/value.txt b/value.txt\n"
        "--- a/value.txt\n"
        "+++ b/value.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "\\ No newline at end of file\n"
        "+new\n"
        "\\ No newline at end of file\n"
    )
    assert patch_paths(no_newline) == {"value.txt"}


@pytest.mark.parametrize(
    "bad_hunk",
    [
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- a/src/file.py\n"
            "+++ b/src/file.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-old\n"
            "+new\n"
        ),
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- a/src/file.py\n"
            "+++ b/src/file.py\n"
            "@@ -one +1 @@\n"
            "-old\n"
            "+new\n"
        ),
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- a/src/file.py\n"
            "+++ b/src/file.py\n"
            "@@ -1 +1 @@\n"
            " old\n"
            "-extra\n"
        ),
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- a/src/file.py\n"
            "+++ b/src/file.py\n"
            "@@ -1,2 +1,2 @@\n"
            " old\n"
            "diff --git a/tests/test_hidden.py b/tests/test_hidden.py\n"
        ),
    ],
)
def test_truncated_malformed_or_overlong_hunks_fail_closed(bad_hunk: str) -> None:
    with pytest.raises(RebenchVerificationError, match="hunk|unexpected content"):
        patch_paths(bad_hunk)


def test_real_binary_patch_is_rejected_even_when_git_applies_it(tmp_path: Path) -> None:
    root = tmp_path / "binary"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    original = bytes(range(256)) * 2
    changed = b"\x00\xff" * 256
    (root / "blob.bin").write_bytes(original)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    (root / "blob.bin").write_bytes(changed)
    patch = _git(root, "diff", "--binary", "--no-ext-diff", "HEAD")
    assert "GIT binary patch" in patch
    with pytest.raises(RebenchVerificationError, match="binary patches are unsupported"):
        patch_paths(patch)

    _git(root, "reset", "--hard", "-q", "HEAD")
    _git(root, "apply", "-p1", "-", input_text=patch)
    assert (root / "blob.bin").read_bytes() == changed


@pytest.mark.parametrize(
    "alias_patch",
    [
        (
            "diff --git a/./conftest.py b/./conftest.py\n"
            "--- a/./conftest.py\n"
            "+++ b/./conftest.py\n"
        ),
        "diff --git a//conftest.py b//conftest.py\n",
        "diff --git a/src/../conftest.py b/src/../conftest.py\n",
        'diff --git "a/./conftest.py" "b/./conftest.py"\n',
        'diff --git "a\\conftest.py" "b\\conftest.py"\n',
        (
            "diff --git a/conftest.py b/renamed.py\n"
            "rename from ./conftest.py\n"
            "rename to renamed.py\n"
        ),
    ],
)
def test_noncanonical_alias_cannot_evade_hidden_conftest_overlap(alias_patch: str) -> None:
    with pytest.raises(RebenchVerificationError, match="noncanonical|unsafe|ambiguous"):
        protected_paths(alias_patch, _patch("conftest.py"))


@pytest.mark.parametrize(
    "patch",
    [
        (
            "diff --git a/src/old.py b/src/new.py\n"
            "rename from src/different.py\n"
            "rename to src/new.py\n"
        ),
        (
            "diff --git a/src/old.py b/src/new.py\n"
            "copy from src/old.py\n"
            "copy to src/different.py\n"
        ),
        (
            "diff --git a/src/file.py b/src/file.py\n"
            "--- a/src/other.py\n"
            "+++ b/src/file.py\n"
        ),
        (
            "diff --git a/src/old.py b/src/new.py\n"
            "rename from src/old.py\n"
        ),
        (
            "diff --git a/src/old.py b/src/new.py\n"
            "rename from src/old.py\n"
            "rename to src/new.py\n"
            "--- /dev/null\n"
            "+++ b/src/new.py\n"
        ),
        "diff --git a/src/old.py b/src/new.py\n",
    ],
)
def test_patch_paths_reject_header_metadata_disagreement(patch: str) -> None:
    with pytest.raises(
        RebenchVerificationError,
        match="disagrees|requires|without matching|cannot use",
    ):
        patch_paths(patch)


def test_changed_protected_path_marker_fails_closed() -> None:
    class MutatingBackend(FakeBackend):
        def run_verifier(self, **kwargs):
            result = super().run_verifier(**kwargs)
            before = hashlib.sha256(b"before").hexdigest()
            after = hashlib.sha256(b"after").hexdigest()
            token = re.search(rf"{MARKER_PREFIX}:([0-9a-f]{{32}}):", kwargs["command"][2]).group(1)
            return DockerRunResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=f"{MARKER_PREFIX}:{token}:{result.returncode}:{before}:{after}\n",
                timed_out=False,
                output_truncated=False,
                container_name=result.container_name,
                command_sha256=result.command_sha256,
            )

    receipt = qualify_task(task(), material(), parser=PINNED_PARSER, backend=MutatingBackend())
    assert receipt["qualified"] is False
    assert all(run["integrity_ok"] is False for run in receipt["runs"])


def test_receipt_hash_detects_tampering() -> None:
    receipt = qualify_task(task(), material(), parser=PINNED_PARSER, backend=FakeBackend())
    tampered = copy.deepcopy(receipt)
    tampered["runs"][0]["expectation_met"] = False
    assert verify_receipt(tampered) is False


def test_task_and_material_contracts_fail_before_any_container() -> None:
    backend = FakeBackend()
    with pytest.raises(RebenchVerificationError, match="reference and digest"):
        qualify_task(
            QualificationTask(
                instance_id="task",
                image_reference=f"registry.example/rebench/task@{DIGEST}",
                image_digest="sha256:" + "c" * 64,
                workdir="/testbed",
            ),
            material(),
            parser=PINNED_PARSER,
            backend=backend,
        )
    with pytest.raises(RebenchVerificationError, match="parser_sha256"):
        qualify_task(task(), material(parser_sha256="nope"), parser=PINNED_PARSER, backend=backend)
    assert backend.calls == []


def test_pinned_parser_loader_binds_exact_file_bytes(tmp_path) -> None:
    parser_file = tmp_path / "parsers.py"
    parser_file.write_text(
        "def parse_log_pytest(output):\n"
        "    return {'test::id': 'passed'} if output else {}\n"
    )
    digest = hashlib.sha256(parser_file.read_bytes()).hexdigest()
    loaded = load_pinned_parser(parser_file, "parse_log_pytest", digest)
    assert loaded("ok") == {"test::id": "passed"}

    with pytest.raises(RebenchVerificationError, match="do not match"):
        load_pinned_parser(parser_file, "parse_log_pytest", "0" * 64)
    with pytest.raises(RebenchVerificationError, match="allowlist"):
        load_pinned_parser(parser_file, "not_a_parser", digest)


def test_unbound_or_mismatched_parser_callable_is_rejected() -> None:
    with pytest.raises(RebenchVerificationError, match="hash-bound"):
        qualify_task(task(), material(), parser=lambda _output: {}, backend=FakeBackend())

    other_source = PARSER_SOURCE + b"\n# different exact source bytes\n"
    other_hash = hashlib.sha256(other_source).hexdigest()
    other = load_pinned_parser_bytes(other_source, "parse_log_pytest", other_hash)
    with pytest.raises(RebenchVerificationError, match="does not match"):
        qualify_task(task(), material(), parser=other, backend=FakeBackend())

    with pytest.raises(AttributeError, match="immutable"):
        PINNED_PARSER._callable = lambda _output: {}

    imported_source = b"from json import loads as parse_log_pytest\n"
    imported_hash = hashlib.sha256(imported_source).hexdigest()
    with pytest.raises(RebenchVerificationError, match="hashed source bytes"):
        load_pinned_parser_bytes(imported_source, "parse_log_pytest", imported_hash)


def _rehash_receipt(receipt: dict) -> None:
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = hashlib.sha256(dump_canonical_json(body)).hexdigest()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["runs"][0].update(returncode=2),
        lambda value: value["runs"][0].update(phase="gold"),
        lambda value: value["runs"][0].update(repeat=2),
        lambda value: value["runs"][0]["fail_to_pass_states"].update(
            {"tests/test_math.py::test_fix": "passed"}
        ),
        lambda value: value["runs"][0].update(parser_ok=False),
        lambda value: value["runs"][0].update(integrity_ok=False),
        lambda value: value.update(base_fail_repeats=1),
        lambda value: value.update(qualified=False),
    ],
)
def test_receipt_rejects_semantic_forgery_even_with_recomputed_self_hash(mutate) -> None:
    forged = qualify_task(task(), material(), parser=PINNED_PARSER, backend=FakeBackend())
    mutate(forged)
    _rehash_receipt(forged)
    assert verify_receipt(forged) is False


def test_image_reference_cannot_begin_with_docker_option_prefix() -> None:
    backend = FakeBackend()
    with pytest.raises(RebenchVerificationError, match="immutable digest"):
        qualify_task(
            QualificationTask(
                instance_id="task",
                image_reference=f"--evil@{DIGEST}",
                image_digest=DIGEST,
                workdir="/testbed",
            ),
            material(),
            parser=PINNED_PARSER,
            backend=backend,
        )
    assert backend.calls == []
