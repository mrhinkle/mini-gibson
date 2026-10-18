from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import tarfile
from pathlib import Path

import pytest

import evaluation.preflight_candidates as preflight
import evaluation.preflight_controller as controller
from evaluation.cohort import dump_canonical_json
from evaluation.docker_backend import DockerRunResult
from evaluation.qualify_candidates import FrozenInputs, QualificationOrchestrationError
from evaluation.verify_rebench import MARKER_PREFIX


DIGEST = "sha256:" + "a" * 64
IMAGE = f"registry.example/rebench/task@{DIGEST}"
GOLD_PATCH = (
    "diff --git a/src/fix.py b/src/fix.py\n"
    "--- a/src/fix.py\n+++ b/src/fix.py\n"
    "@@ -1 +1 @@\n-old\n+new\n"
)
TEST_PATCH = (
    "diff --git a/tests/test_fix.py b/tests/test_fix.py\n"
    "--- a/tests/test_fix.py\n+++ b/tests/test_fix.py\n"
    "@@ -1 +1 @@\n-weak\n+strict\n"
)


class MechanicsBackend:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.calls = 0
        self.fail_first = fail_first

    def run_verifier(self, *, image, workdir, command, stdin, timeout_s):
        with tarfile.open(fileobj=io.BytesIO(stdin), mode="r:") as archive:
            assert archive.extractfile("test-command").read() == b"true"
        token = re.search(rf"{MARKER_PREFIX}:([0-9a-f]{{32}}):", command[2]).group(1)
        digest = hashlib.sha256(b"protected").hexdigest()
        failing = self.fail_first and self.calls == 0
        index = self.calls
        self.calls += 1
        return DockerRunResult(
            returncode=84 if failing else 0,
            stdout="",
            stderr=(
                ""
                if failing
                else f"{MARKER_PREFIX}:{token}:0:{digest}:{digest}\n"
            ),
            timed_out=False,
            output_truncated=False,
            container_name=f"mini-gibson-verifier-{index:012x}",
            command_sha256=hashlib.sha256(str(index).encode()).hexdigest(),
        )


def frozen_inputs(tmp_path: Path) -> FrozenInputs:
    candidates = [
        {
            "instance_id": f"owner__repo-{index}",
            "selection_rank": index,
            "base_commit": "b" * 40,
        }
        for index in (1, 2)
    ]
    plan = {
        "cohorts": [
            {
                "cohort_id": "pilot-budget",
                "candidate_report": {"candidates": candidates},
            }
        ]
    }
    materials = {
        candidate["instance_id"]: {
            "gold_patch": GOLD_PATCH,
            "test_patch": TEST_PATCH,
            "fail_to_pass": ["tests/test_fix.py::test_fix"],
            "pass_to_pass": [],
            "install_config": {
                "test_cmd": "pytest -q",
                "log_parser": "parse_log_pytest",
            },
        }
        for candidate in candidates
    }
    images = {
        candidate["instance_id"]: {
            "instance_id": candidate["instance_id"],
            "image_name": "registry.example/rebench/task:fixed",
            "reference": IMAGE,
            "digest": DIGEST,
            "workdir": "/testbed",
        }
        for candidate in candidates
    }
    digest = lambda value: hashlib.sha256(value).hexdigest()
    invariants = {
        "candidate_plan_sha256": digest(b"plan"),
        "dataset_revision": "frozen-revision",
        "dataset_sha256": digest(b"dataset"),
        "material_package_sha256": digest(b"materials"),
        "image_lock_sha256": digest(b"images"),
        "tooling": {
            "docker_backend_sha256": digest(b"docker"),
            "verifier_sha256": digest(b"verifier"),
        },
        "candidate_count": 2,
    }
    empty = tmp_path / "unused"
    return FrozenInputs(
        repo_root=tmp_path,
        plan_path=empty,
        registry_path=empty,
        evidence_path=empty,
        dataset_path=empty,
        material_package_path=empty,
        image_lock_path=empty,
        plan=plan,
        registry={},
        evidence={},
        dataset_records={},
        materials=materials,
        parser_sources={"parse_log_pytest": b"def parse_log_pytest(_): return {}\n"},
        images=images,
        invariants=invariants,
    )


def test_preflight_continues_after_incompatibility_and_finalizes(tmp_path: Path) -> None:
    inputs = frozen_inputs(tmp_path)
    invariants = preflight.preflight_invariants(inputs)
    expected = ["owner__repo-1", "owner__repo-2"]
    journal_path = tmp_path / "preflight.jsonl"
    output_path = tmp_path / "manifest.json"
    backend = MechanicsBackend(fail_first=True)

    with preflight.PreflightJournal(journal_path, invariants, expected) as journal:
        status = preflight.run_pending(
            inputs,
            journal,
            backend=backend,
            image_verifier=lambda _image: None,
            invariants=invariants,
        )
        manifest = preflight.finalize(inputs, journal, output_path, invariants)

    assert backend.calls == 4
    assert status == {
        "processed_this_invocation": 2,
        "recorded": 2,
        "compatible": 1,
        "incompatible": 1,
        "remaining": 0,
        "complete": True,
        "journal_head_sha256": status["journal_head_sha256"],
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }
    assert manifest["status"] == "preflight_complete_incompatible"
    assert manifest["incompatible_instance_ids"] == ["owner__repo-1"]
    assert json.loads(output_path.read_text()) == manifest


def test_preflight_resume_audits_binding_and_refuses_reclassification(tmp_path: Path) -> None:
    inputs = frozen_inputs(tmp_path)
    invariants = preflight.preflight_invariants(inputs)
    expected = ["owner__repo-1", "owner__repo-2"]
    journal_path = tmp_path / "preflight.jsonl"

    with preflight.PreflightJournal(journal_path, invariants, expected) as journal:
        preflight.run_pending(
            inputs,
            journal,
            backend=MechanicsBackend(),
            image_verifier=lambda _image: None,
            invariants=invariants,
            limit=1,
        )
        receipt = journal.records["owner__repo-1"]["receipt"]
        with pytest.raises(QualificationOrchestrationError, match="reclassify"):
            journal.append(
                cohort_id="pilot-budget",
                selection_rank=1,
                instance_id="owner__repo-1",
                input_sha256="a" * 64,
                receipt=receipt,
            )

    lines = journal_path.read_bytes().splitlines(keepends=True)
    changed = json.loads(lines[-1])
    changed["input_sha256"] = "c" * 64
    changed["record_sha256"] = preflight._record_hash(changed)
    lines[-1] = dump_canonical_json(changed)
    journal_path.write_bytes(b"".join(lines))

    with preflight.PreflightJournal(journal_path, invariants, expected) as journal:
        with pytest.raises(QualificationOrchestrationError, match="binding disagrees"):
            preflight.run_pending(
                inputs,
                journal,
                backend=MechanicsBackend(),
                image_verifier=lambda _image: None,
                invariants=invariants,
            )


def test_preflight_journal_rejects_malformed_input_hash(tmp_path: Path) -> None:
    inputs = frozen_inputs(tmp_path)
    invariants = preflight.preflight_invariants(inputs)
    expected = ["owner__repo-1", "owner__repo-2"]
    candidate = inputs.plan["cohorts"][0]["candidate_report"]["candidates"][0]
    receipt, _input_sha = preflight._preflight_one(
        inputs,
        candidate,
        backend=MechanicsBackend(),
        image_verifier=lambda _image: None,
        invariants=invariants,
    )
    with preflight.PreflightJournal(
        tmp_path / "preflight.jsonl", invariants, expected
    ) as journal:
        with pytest.raises(QualificationOrchestrationError, match="lowercase SHA-256"):
            journal.append(
                cohort_id="pilot-budget",
                selection_rank=1,
                instance_id="owner__repo-1",
                input_sha256="not-a-sha",
                receipt=receipt,
            )


def test_controller_bounds_registry_output_and_classifies_rate_limits() -> None:
    bounded = controller._run_bounded(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 10000)"],
        timeout_s=5,
        max_output_bytes=128,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert bounded.truncated is True
    assert len(bounded.output) == 128
    assert controller._pull_classification(bounded) == "output_limit"

    rate_limited = controller.BoundedCommandResult(
        returncode=1,
        output=b"error: toomanyrequests: rate limit exceeded",
        truncated=False,
        timed_out=False,
    )
    assert controller._pull_classification(rate_limited) == "rate_limited"

    digest_only = controller.BoundedCommandResult(
        returncode=1,
        output=(
            b"manifest unknown for image@sha256:"
            + b"a" * 40
            + b"429"
            + b"b" * 21
        ),
        truncated=False,
        timed_out=False,
    )
    assert controller._pull_classification(digest_only) == "failed"
