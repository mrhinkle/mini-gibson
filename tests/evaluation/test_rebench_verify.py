from __future__ import annotations

import copy
import hashlib
import io
import re
import tarfile

import pytest

from evaluation.docker_backend import DockerIsolationError, DockerRunResult
from evaluation.verify_rebench import (
    MARKER_PREFIX,
    QualificationTask,
    RebenchVerificationError,
    VerifierMaterial,
    load_pinned_parser,
    patch_paths,
    qualify_task,
    verify_receipt,
)


DIGEST = "sha256:" + "b" * 64


def _patch(path: str, before: str = "old", after: str = "new") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        f"-{before}\n"
        f"+{after}\n"
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
        "parser_sha256": hashlib.sha256(b"pinned parser").hexdigest(),
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


def parser(output: str) -> dict[str, str]:
    state = "passed" if "GOLD" in output else "failed"
    return {
        "tests/test_math.py::test_fix": state,
        "tests/test_math.py::test_existing": "passed",
    }


def test_qualification_requires_two_fresh_base_fails_and_gold_passes() -> None:
    backend = FakeBackend()
    receipt = qualify_task(task(), material(), parser=parser, backend=backend)

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
    receipt = qualify_task(task(), material(), parser=parser, backend=FakeBackend(overrides))
    assert receipt["qualified"] is False
    assert verify_receipt(receipt) is True
    assert any(not run["expectation_met"] for run in receipt["runs"])


def test_parser_failure_or_missing_required_status_fails_closed() -> None:
    def explode(_output):
        raise RuntimeError("bad parser output")

    failed = qualify_task(task(), material(), parser=explode, backend=FakeBackend())
    assert failed["qualified"] is False
    assert all(run["parser_ok"] is False for run in failed["runs"])

    missing = qualify_task(task(), material(), parser=lambda _output: {}, backend=FakeBackend())
    assert missing["qualified"] is False
    assert all("missing" in run["fail_to_pass_states"].values() for run in missing["runs"])


def test_docker_failure_is_recorded_and_does_not_skip_other_repeats() -> None:
    backend = FakeBackend(docker_error_at=1)
    receipt = qualify_task(task(), material(), parser=parser, backend=backend)
    assert receipt["qualified"] is False
    assert len(backend.calls) == 4
    assert "Docker isolation failed" in receipt["runs"][1]["error"]


def test_product_patch_cannot_touch_hidden_or_conventional_test_paths() -> None:
    with pytest.raises(RebenchVerificationError, match="protected test paths"):
        qualify_task(
            task(),
            material(gold_patch=_patch("tests/test_math.py", "wrong", "cheat")),
            parser=parser,
            backend=FakeBackend(),
        )
    with pytest.raises(RebenchVerificationError, match="protected test paths"):
        qualify_task(
            task(),
            material(gold_patch=_patch("spec/math.spec.ts")),
            parser=parser,
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

    receipt = qualify_task(task(), material(), parser=parser, backend=MutatingBackend())
    assert receipt["qualified"] is False
    assert all(run["integrity_ok"] is False for run in receipt["runs"])


def test_receipt_hash_detects_tampering() -> None:
    receipt = qualify_task(task(), material(), parser=parser, backend=FakeBackend())
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
            parser=parser,
            backend=backend,
        )
    with pytest.raises(RebenchVerificationError, match="parser_sha256"):
        qualify_task(task(), material(parser_sha256="nope"), parser=parser, backend=backend)
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
