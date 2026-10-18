from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import evaluation.qualify_candidates as orchestrator
from evaluation.cohort import dump_canonical_json
from evaluation.docker_backend import DockerRunResult
from evaluation.qualify_candidates import (
    HashChainJournal,
    QualificationOrchestrationError,
    _read_image_lock,
    _record_hash,
    _reject_holdout_paths,
    _test_id_list,
    dry_run_report,
    run_pending,
)
from evaluation.verify_rebench import (
    MARKER_PREFIX,
    QualificationTask,
    VerifierMaterial,
    load_pinned_parser_bytes,
    qualify_task,
)


PARSER_SOURCE = b"""def parse_log_pytest(output):
    return {"tests/test_fix.py::test_fix": "passed" if "GOLD" in output else "failed"}
"""
PARSER_SHA = hashlib.sha256(PARSER_SOURCE).hexdigest()
PARSER = load_pinned_parser_bytes(PARSER_SOURCE, "parse_log_pytest", PARSER_SHA)
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
NATCAP_DIGEST = "sha256:09439f2cb8d17177ab148b29d22fb9b14bc7e9981c31872b62fd39dfb0b91627"
NATCAP_REFERENCE = f"docker.io/swerebenchv2/natcap-invest@{NATCAP_DIGEST}"
REPO_ROOT = Path(__file__).resolve().parents[2]


class ReceiptBackend:
    def __init__(self) -> None:
        self.calls = 0

    def run_verifier(self, *, image, workdir, command, stdin, timeout_s):
        with tarfile.open(fileobj=io.BytesIO(stdin), mode="r:") as archive:
            product = archive.extractfile("product.patch").read()
        token = re.search(rf"{MARKER_PREFIX}:([0-9a-f]{{32}}):", command[2]).group(1)
        phase = "gold" if product else "base"
        protected = hashlib.sha256(b"protected").hexdigest()
        index = self.calls
        self.calls += 1
        return DockerRunResult(
            returncode=0 if phase == "gold" else 1,
            stdout=phase.upper(),
            stderr=f"{MARKER_PREFIX}:{token}:{0 if phase == 'gold' else 1}:{protected}:{protected}\n",
            timed_out=False,
            output_truncated=False,
            container_name=f"mini-gibson-verifier-{index:012x}",
            command_sha256=hashlib.sha256(str(index).encode()).hexdigest(),
        )


def patch(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )


def valid_receipt(instance_id: str) -> dict:
    return qualify_task(
        QualificationTask(
            instance_id=instance_id,
            base_commit="a" * 40,
            image_reference=f"registry.example/task@{DIGEST}",
            image_digest=DIGEST,
            workdir="/testbed",
        ),
        VerifierMaterial(
            gold_patch=patch("src/fix.py"),
            test_patch=patch("tests/test_fix.py"),
            fail_to_pass=("tests/test_fix.py::test_fix",),
            pass_to_pass=(),
            test_command="pytest -q",
            parser_name="parse_log_pytest",
            parser_sha256=PARSER_SHA,
        ),
        parser=PARSER,
        backend=ReceiptBackend(),
    )


def tiny_plan() -> dict:
    return {
        "cohorts": [
            {
                "cohort_id": "pilot-budget",
                "candidate_report": {
                    "candidates": [
                        {"instance_id": "owner__repo-1", "selection_rank": 1},
                        {"instance_id": "owner__repo-2", "selection_rank": 2},
                    ]
                },
            }
        ]
    }


def test_test_id_list_preserves_multiline_parser_keys() -> None:
    value = ["Compiles: fun test() {\n    println()\n} (ExampleSpec)"]
    assert _test_id_list(value, "fail_to_pass", required=True) == tuple(value)

    for bad in ("", "bad\0selector", "bad\rselector"):
        with pytest.raises(QualificationOrchestrationError, match="without NUL"):
            _test_id_list([bad], "fail_to_pass", required=True)

    with pytest.raises(QualificationOrchestrationError, match="duplicate"):
        _test_id_list(["same", "same"], "fail_to_pass", required=True)


def tiny_inputs(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        plan=tiny_plan(),
        invariants={"plan": hashlib.sha256(b"plan").hexdigest()},
    )


def test_crash_resume_skips_prior_receipt_without_reclassification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tiny_inputs(tmp_path)
    journal_path = tmp_path / "qualification.jsonl"
    expected = ["owner__repo-1", "owner__repo-2"]
    first_calls: list[str] = []
    monkeypatch.setattr(orchestrator, "audit_journal_bindings", lambda *_args: None)

    def crash_on_second(_inputs, candidate, **_kwargs):
        instance_id = candidate["instance_id"]
        first_calls.append(instance_id)
        if instance_id.endswith("-2"):
            raise KeyboardInterrupt("simulated interruption")
        return valid_receipt(instance_id), hashlib.sha256(instance_id.encode()).hexdigest()

    monkeypatch.setattr(orchestrator, "_qualify_one", crash_on_second)
    with pytest.raises(KeyboardInterrupt):
        with HashChainJournal(journal_path, inputs.invariants, expected) as journal:
            run_pending(inputs, journal, backend=object(), image_verifier=lambda _entry: None)
    assert first_calls == expected

    resumed_calls: list[str] = []

    def complete(_inputs, candidate, **_kwargs):
        instance_id = candidate["instance_id"]
        resumed_calls.append(instance_id)
        return valid_receipt(instance_id), hashlib.sha256(instance_id.encode()).hexdigest()

    monkeypatch.setattr(orchestrator, "_qualify_one", complete)
    with HashChainJournal(journal_path, inputs.invariants, expected) as journal:
        run_pending(inputs, journal, backend=object(), image_verifier=lambda _entry: None)
        assert set(journal.records) == set(expected)
    assert resumed_calls == ["owner__repo-2"]


def test_duplicate_and_tampered_journal_records_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    invariants = {"plan": "frozen"}
    receipt = valid_receipt("owner__repo-1")
    with HashChainJournal(path, invariants, ["owner__repo-1"]) as journal:
        journal.append(
            cohort_id="pilot-budget",
            selection_rank=1,
            instance_id="owner__repo-1",
            input_sha256=hashlib.sha256(b"input").hexdigest(),
            receipt=receipt,
        )
        with pytest.raises(QualificationOrchestrationError, match="reclassify"):
            journal.append(
                cohort_id="pilot-budget",
                selection_rank=1,
                instance_id="owner__repo-1",
                input_sha256=hashlib.sha256(b"input").hexdigest(),
                receipt=receipt,
            )

    lines = path.read_bytes().splitlines(keepends=True)
    changed = json.loads(lines[1])
    changed["selection_rank"] = 9
    lines[1] = dump_canonical_json(changed)
    path.write_bytes(b"".join(lines))
    with pytest.raises(QualificationOrchestrationError, match="hash chain"):
        with HashChainJournal(path, invariants, ["owner__repo-1"]):
            pass


def test_incomplete_receipt_is_rejected_even_with_valid_record_chain(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    invariants = {"plan": "frozen"}
    with HashChainJournal(path, invariants, ["owner__repo-1"]):
        pass
    header = json.loads(path.read_text().splitlines()[0])
    record = {
        "schema_version": orchestrator.JOURNAL_SCHEMA,
        "record_type": "qualification_receipt",
        "sequence": 1,
        "previous_record_sha256": header["record_sha256"],
        "cohort_id": "pilot-budget",
        "selection_rank": 1,
        "instance_id": "owner__repo-1",
        "input_sha256": hashlib.sha256(b"input").hexdigest(),
        "receipt": {"qualified": True},
    }
    record["record_sha256"] = _record_hash(record)
    with path.open("ab") as handle:
        handle.write(dump_canonical_json(record))
    with pytest.raises(QualificationOrchestrationError, match="incomplete"):
        with HashChainJournal(path, invariants, ["owner__repo-1"]):
            pass


def image_plan() -> dict:
    candidates = [
        {
            "instance_id": "owner__repo-1",
            "image_name": "docker.io/swerebenchv2/repo:one",
        }
    ]
    return {
        "cohorts": [
            {"cohort_id": "pilot-budget", "candidate_report": {"candidates": candidates}}
        ]
    }


def test_image_reference_digest_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = image_plan()
    monkeypatch.setattr(orchestrator, "canonical_plan_sha256", lambda _plan: "b" * 64)
    lock = {
        "schema_version": orchestrator.IMAGE_LOCK_SCHEMA,
        "source": {
            "dataset": orchestrator.DATASET,
            "revision": orchestrator.DATASET_REVISION,
            "split": "train",
            "file": orchestrator.DATASET_FILE,
            "sha256": orchestrator.SOURCE_SHA256,
            "rows": orchestrator.SOURCE_ROWS,
        },
        "candidate_plan_sha256": "b" * 64,
        "platform": "linux/amd64",
        "entries": [
            {
                "instance_id": "owner__repo-1",
                "image_name": "docker.io/swerebenchv2/repo:one",
                "reference": f"docker.io/swerebenchv2/other@{DIGEST}",
                "digest": DIGEST,
                "workdir": "/testbed",
            }
        ],
    }
    path = tmp_path / "images.json"
    path.write_text(json.dumps(lock))
    with pytest.raises(QualificationOrchestrationError, match="reference/tag/digest"):
        _read_image_lock(path, plan)


def _mock_image_inspect(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repo_digests: object,
    os_name: str = "linux",
    architecture: str = "amd64",
    workdir: str = "/testbed",
) -> list[list[str]]:
    calls: list[list[str]] = []

    def inspect(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "RepoDigests": repo_digests,
                        "Os": os_name,
                        "Architecture": architecture,
                        "Config": {"WorkingDir": workdir},
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(orchestrator.subprocess, "run", inspect)
    return calls


def _natcap_image_entry() -> dict[str, str]:
    return {
        "instance_id": "natcap__invest-1365",
        "image_name": "docker.io/swerebenchv2/natcap-invest:1365-6db2256",
        "reference": NATCAP_REFERENCE,
        "digest": NATCAP_DIGEST,
        "workdir": "/testbed",
    }


@pytest.mark.parametrize(
    "inspected_reference",
    [NATCAP_REFERENCE, f"swerebenchv2/natcap-invest@{NATCAP_DIGEST}"],
)
def test_verify_local_image_accepts_exact_natcap_docker_hub_normalization(
    monkeypatch: pytest.MonkeyPatch,
    inspected_reference: str,
) -> None:
    calls = _mock_image_inspect(monkeypatch, repo_digests=[inspected_reference])

    orchestrator.verify_local_image(_natcap_image_entry())

    assert calls == [["docker", "image", "inspect", NATCAP_REFERENCE]]


@pytest.mark.parametrize(
    "inspected_reference",
    [
        f"ghcr.io/swerebenchv2/natcap-invest@{NATCAP_DIGEST}",
        f"index.docker.io/swerebenchv2/natcap-invest@{NATCAP_DIGEST}",
        f"swerebenchv2/other-repository@{NATCAP_DIGEST}",
        f"swerebenchv2/natcap-invest@{OTHER_DIGEST}",
    ],
)
def test_verify_local_image_rejects_wrong_registry_repository_or_digest(
    monkeypatch: pytest.MonkeyPatch,
    inspected_reference: str,
) -> None:
    _mock_image_inspect(monkeypatch, repo_digests=[inspected_reference])

    with pytest.raises(QualificationOrchestrationError, match="locked digest/platform/workdir"):
        orchestrator.verify_local_image(_natcap_image_entry())


@pytest.mark.parametrize(
    "metadata_override",
    [
        {"os_name": "windows"},
        {"architecture": "arm64"},
        {"workdir": "/workspace"},
    ],
)
def test_verify_local_image_rejects_platform_or_workdir_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    metadata_override: dict[str, str],
) -> None:
    _mock_image_inspect(
        monkeypatch,
        repo_digests=[f"swerebenchv2/natcap-invest@{NATCAP_DIGEST}"],
        **metadata_override,
    )

    with pytest.raises(QualificationOrchestrationError, match="locked digest/platform/workdir"):
        orchestrator.verify_local_image(_natcap_image_entry())


def test_dry_run_never_invokes_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = SimpleNamespace(plan=tiny_plan(), invariants={"plan": "frozen"})
    monkeypatch.setattr(
        orchestrator.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("dry-run invoked Docker"),
    )
    report = dry_run_report(inputs, tmp_path / "missing.jsonl")
    assert report["docker_pulls"] == report["docker_runs"] == 0
    assert report["final_holdout_status"] == "sealed_not_read_or_run"


def test_holdout_paths_are_rejected_without_access(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    holdout = repo / "bench" / "manifest.v0.1.json"
    with pytest.raises(QualificationOrchestrationError, match="holdout boundary"):
        _reject_holdout_paths(repo, [holdout])
    outside = tmp_path / "pinned.parquet"
    _reject_holdout_paths(repo, [outside])


def test_partial_finalization_never_creates_runnable_manifest(tmp_path: Path) -> None:
    inputs = tiny_inputs(tmp_path)
    journal_path = tmp_path / "journal.jsonl"
    with HashChainJournal(
        journal_path, inputs.invariants, ["owner__repo-1", "owner__repo-2"]
    ) as journal:
        with pytest.raises(QualificationOrchestrationError, match="every frozen candidate"):
            orchestrator.finalize(inputs, journal, tmp_path / "out")
    assert not (tmp_path / "out" / "qualification-final-manifest.json").exists()


def test_committed_freeze_authorities_match_orchestrator_pins() -> None:
    root = REPO_ROOT / "evaluation/frozen/mini-gibson-v2-sequential-2026-10-17"
    plan = json.loads((root / "sequential-plan.json").read_text())
    registry = json.loads((root / "pre-plan-exclusions.json").read_text())
    assert orchestrator.canonical_plan_sha256(plan) == orchestrator.FROZEN_PLAN_CANONICAL_SHA256
    assert orchestrator._canonical_sha256(registry) == orchestrator.FROZEN_REGISTRY_CANONICAL_SHA256
    assert orchestrator._sha256_file(root / "sequential-plan.json") == orchestrator.FROZEN_PLAN_FILE_SHA256
    assert orchestrator._sha256_file(root / "pre-plan-exclusions.json") == orchestrator.FROZEN_REGISTRY_FILE_SHA256
    assert orchestrator._sha256_file(root / "freeze-evidence.json") == orchestrator.FROZEN_EVIDENCE_FILE_SHA256
