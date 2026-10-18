"""Outcome-blind, resumable compatibility preflight for frozen SWE-rebench images.

This command exercises only repository and patch mechanics under the exact
future verifier container boundary. It never runs the task test command, a
parser, a model, or an agent, and it never reads the final holdout. Every
candidate receives one base-path and one gold-path mechanics run in fresh
containers. The complete 456-row matrix is required before a successor
qualification experiment can be frozen.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, BinaryIO

from .cohort import dump_canonical_json
from .docker_backend import DockerBackend
from .qualify_candidates import (
    FrozenInputs,
    QualificationOrchestrationError,
    _atomic_write,
    _candidate_sequence,
    _canonical_sha256,
    _sha256,
    _sha256_bytes,
    _sha256_file,
    load_frozen_inputs,
    verify_local_image,
)
from .verify_rebench import (
    QualificationTask,
    VerifierMaterial,
    preflight_task,
    verify_preflight_receipt,
)


JOURNAL_SCHEMA = "mini-gibson-compatibility-preflight-journal/v1"
MANIFEST_SCHEMA = "mini-gibson-compatibility-preflight-manifest/v1"
ZERO_SHA256 = "0" * 64
PREDECESSOR_TERMINAL_RECEIPT_SHA256 = (
    "063304b83ce4b5b36200f480e38164782d6fed3aa05277a4568b2e98bcdc01b2"
)
HEADER_KEYS = {
    "schema_version",
    "record_type",
    "sequence",
    "previous_record_sha256",
    "invariants",
    "record_sha256",
}
RECORD_KEYS = {
    "schema_version",
    "record_type",
    "sequence",
    "previous_record_sha256",
    "cohort_id",
    "selection_rank",
    "instance_id",
    "input_sha256",
    "receipt",
    "record_sha256",
}


def _record_hash(record: Mapping[str, Any]) -> str:
    body = dict(record)
    body.pop("record_sha256", None)
    return _canonical_sha256(body)


def preflight_invariants(inputs: FrozenInputs) -> dict[str, Any]:
    return {
        **inputs.invariants,
        "preflight_module_sha256": _sha256_file(Path(__file__)),
        "preflight_controller_sha256": _sha256_file(
            Path(__file__).with_name("preflight_controller.py")
        ),
        "predecessor_experiment": "mini-gibson-v2-2026-10-18",
        "predecessor_terminal_receipt_sha256": PREDECESSOR_TERMINAL_RECEIPT_SHA256,
        "preflight_scope": "all_456_candidates_base_and_gold_patch_mechanics_no_tests",
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }


class PreflightJournal:
    """Exclusive append-only compatibility journal in frozen candidate order."""

    def __init__(
        self,
        path: Path,
        invariants: Mapping[str, Any],
        expected_ids: Sequence[str],
    ) -> None:
        self.path = path
        self.invariants = dict(invariants)
        self.expected_ids = tuple(expected_ids)
        self._lock_handle: BinaryIO | None = None
        self.records: dict[str, Mapping[str, Any]] = {}
        self.last_sha256 = ZERO_SHA256
        self.next_sequence = 0

    def __enter__(self) -> PreflightJournal:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise QualificationOrchestrationError("preflight journal cannot be a symlink")
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        if lock_path.is_symlink():
            raise QualificationOrchestrationError("preflight journal lock cannot be a symlink")
        self._lock_handle = lock_path.open("a+b")
        fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self._load_or_initialize()
        return self

    def __exit__(self, *_args: object) -> None:
        if self._lock_handle is not None:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None

    def _append_bytes(self, payload: bytes) -> None:
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            if os.write(descriptor, payload) != len(payload):
                raise QualificationOrchestrationError("short append to preflight journal")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _load_or_initialize(self) -> None:
        if not self.path.exists():
            header: dict[str, Any] = {
                "schema_version": JOURNAL_SCHEMA,
                "record_type": "header",
                "sequence": 0,
                "previous_record_sha256": ZERO_SHA256,
                "invariants": self.invariants,
            }
            header["record_sha256"] = _record_hash(header)
            self._append_bytes(dump_canonical_json(header))
        self._load()

    def _load(self) -> None:
        self.records = {}
        previous = ZERO_SHA256
        try:
            lines = self.path.read_bytes().splitlines(keepends=True)
        except OSError as exc:
            raise QualificationOrchestrationError(f"cannot read preflight journal: {exc}") from exc
        if not lines or any(not line.endswith(b"\n") for line in lines):
            raise QualificationOrchestrationError("preflight journal has an incomplete record")
        for sequence, line in enumerate(lines):
            try:
                record = json.loads(line)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise QualificationOrchestrationError(
                    f"preflight journal record {sequence} is invalid JSON"
                ) from exc
            expected_keys = HEADER_KEYS if sequence == 0 else RECORD_KEYS
            if not isinstance(record, dict) or set(record) != expected_keys:
                raise QualificationOrchestrationError(
                    f"preflight journal record {sequence} has unexpected fields"
                )
            if (
                record["schema_version"] != JOURNAL_SCHEMA
                or record["sequence"] != sequence
                or record["previous_record_sha256"] != previous
                or record["record_sha256"] != _record_hash(record)
            ):
                raise QualificationOrchestrationError(
                    f"preflight journal record {sequence} breaks the hash chain"
                )
            if sequence == 0:
                if record["record_type"] != "header" or record["invariants"] != self.invariants:
                    raise QualificationOrchestrationError("preflight journal invariants disagree")
            else:
                instance_id = record["instance_id"]
                if (
                    record["record_type"] != "compatibility_receipt"
                    or sequence > len(self.expected_ids)
                    or instance_id != self.expected_ids[sequence - 1]
                    or instance_id in self.records
                    or not verify_preflight_receipt(record["receipt"])
                    or record["receipt"]["instance_id"] != instance_id
                ):
                    raise QualificationOrchestrationError(
                        f"preflight journal record {sequence} is invalid or out of order"
                    )
                self.records[instance_id] = record
            previous = record["record_sha256"]
        self.last_sha256 = previous
        self.next_sequence = len(lines)

    def append(
        self,
        *,
        cohort_id: str,
        selection_rank: int,
        instance_id: str,
        input_sha256: str,
        receipt: Mapping[str, Any],
    ) -> None:
        if instance_id in self.records:
            raise QualificationOrchestrationError(
                f"refusing to reclassify prior preflight task {instance_id}"
            )
        if (
            self.next_sequence > len(self.expected_ids)
            or instance_id != self.expected_ids[self.next_sequence - 1]
            or not verify_preflight_receipt(receipt)
            or receipt["instance_id"] != instance_id
        ):
            raise QualificationOrchestrationError("refusing invalid or out-of-order preflight receipt")
        record: dict[str, Any] = {
            "schema_version": JOURNAL_SCHEMA,
            "record_type": "compatibility_receipt",
            "sequence": self.next_sequence,
            "previous_record_sha256": self.last_sha256,
            "cohort_id": cohort_id,
            "selection_rank": selection_rank,
            "instance_id": instance_id,
            "input_sha256": _sha256(input_sha256, "input_sha256"),
            "receipt": receipt,
        }
        record["record_sha256"] = _record_hash(record)
        self._append_bytes(dump_canonical_json(record))
        self._load()


def _input_sha256(
    candidate: Mapping[str, Any],
    material: Mapping[str, Any],
    image: Mapping[str, Any],
    invariants: Mapping[str, Any],
) -> str:
    return _canonical_sha256(
        {
            "candidate": candidate,
            "material_sha256": _canonical_sha256(material),
            "image": image,
            "preflight_module_sha256": invariants["preflight_module_sha256"],
            "docker_backend_sha256": invariants["tooling"]["docker_backend_sha256"],
            "verifier_sha256": invariants["tooling"]["verifier_sha256"],
            "predecessor_terminal_receipt_sha256": PREDECESSOR_TERMINAL_RECEIPT_SHA256,
        }
    )


def _preflight_one(
    inputs: FrozenInputs,
    candidate: Mapping[str, Any],
    *,
    backend: DockerBackend,
    image_verifier: Callable[[Mapping[str, Any]], None],
    invariants: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    instance_id = candidate["instance_id"]
    material = inputs.materials[instance_id]
    image = inputs.images[instance_id]
    image_verifier(image)
    install = material["install_config"]
    receipt = preflight_task(
        QualificationTask(
            instance_id=instance_id,
            base_commit=candidate["base_commit"],
            image_reference=image["reference"],
            image_digest=image["digest"],
            workdir=image["workdir"],
            verify_timeout_s=900,
        ),
        VerifierMaterial(
            gold_patch=material["gold_patch"],
            test_patch=material["test_patch"],
            fail_to_pass=tuple(material["fail_to_pass"]),
            pass_to_pass=tuple(material["pass_to_pass"]),
            test_command=install["test_cmd"],
            parser_name=install["log_parser"],
            parser_sha256=_sha256_bytes(inputs.parser_sources[install["log_parser"]]),
        ),
        backend=backend,
    )
    return receipt, _input_sha256(candidate, material, image, invariants)


def _validate_prior_record_binding(
    inputs: FrozenInputs,
    cohort_id: str,
    candidate: Mapping[str, Any],
    record: Mapping[str, Any],
    invariants: Mapping[str, Any],
) -> None:
    instance_id = candidate["instance_id"]
    material = inputs.materials[instance_id]
    image = inputs.images[instance_id]
    receipt = record["receipt"]
    expected_fields = {
        "instance_id": instance_id,
        "base_commit": candidate["base_commit"],
        "image_reference": image["reference"],
        "image_digest": image["digest"],
        "workdir": image["workdir"],
        "verify_timeout_s": 900,
        "gold_patch_sha256": _sha256_bytes(material["gold_patch"].encode()),
        "test_patch_sha256": _sha256_bytes(material["test_patch"].encode()),
        "test_command_sha256": _sha256_bytes(
            material["install_config"]["test_cmd"].encode()
        ),
        "mechanics_command_sha256": _sha256_bytes(b"true"),
    }
    expected_input = _input_sha256(candidate, material, image, invariants)
    if (
        record["cohort_id"] != cohort_id
        or record["selection_rank"] != candidate["selection_rank"]
        or record["input_sha256"] != expected_input
    ):
        raise QualificationOrchestrationError(
            f"prior preflight binding disagrees for {instance_id}"
        )
    for field, expected in expected_fields.items():
        if receipt[field] != expected:
            raise QualificationOrchestrationError(
                f"prior preflight receipt field {field!r} disagrees for {instance_id}"
            )


def audit_journal_bindings(
    inputs: FrozenInputs,
    journal: PreflightJournal,
    invariants: Mapping[str, Any],
) -> None:
    for cohort_id, candidate in _candidate_sequence(inputs.plan):
        record = journal.records.get(candidate["instance_id"])
        if record is not None:
            _validate_prior_record_binding(
                inputs, cohort_id, candidate, record, invariants
            )


def run_pending(
    inputs: FrozenInputs,
    journal: PreflightJournal,
    *,
    backend: DockerBackend,
    image_verifier: Callable[[Mapping[str, Any]], None],
    invariants: Mapping[str, Any],
    limit: int | None = None,
) -> dict[str, Any]:
    audit_journal_bindings(inputs, journal, invariants)
    processed = 0
    for cohort_id, candidate in _candidate_sequence(inputs.plan):
        instance_id = candidate["instance_id"]
        if instance_id in journal.records:
            continue
        if limit is not None and processed >= limit:
            break
        receipt, input_sha = _preflight_one(
            inputs,
            candidate,
            backend=backend,
            image_verifier=image_verifier,
            invariants=invariants,
        )
        journal.append(
            cohort_id=cohort_id,
            selection_rank=candidate["selection_rank"],
            instance_id=instance_id,
            input_sha256=input_sha,
            receipt=receipt,
        )
        processed += 1
    compatible = sum(bool(row["receipt"]["compatible"]) for row in journal.records.values())
    return {
        "processed_this_invocation": processed,
        "recorded": len(journal.records),
        "compatible": compatible,
        "incompatible": len(journal.records) - compatible,
        "remaining": len(journal.expected_ids) - len(journal.records),
        "complete": len(journal.records) == len(journal.expected_ids),
        "journal_head_sha256": journal.last_sha256,
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }


def finalize(
    inputs: FrozenInputs,
    journal: PreflightJournal,
    output_path: Path,
    invariants: Mapping[str, Any],
) -> Mapping[str, Any]:
    audit_journal_bindings(inputs, journal, invariants)
    if len(journal.records) != len(journal.expected_ids):
        raise QualificationOrchestrationError("cannot finalize incomplete compatibility preflight")
    compatible = sum(bool(row["receipt"]["compatible"]) for row in journal.records.values())
    incompatible_ids = [
        instance_id
        for instance_id in journal.expected_ids
        if not journal.records[instance_id]["receipt"]["compatible"]
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "status": (
            "preflight_complete_compatible"
            if not incompatible_ids
            else "preflight_complete_incompatible"
        ),
        "candidate_count": len(journal.expected_ids),
        "compatible_count": compatible,
        "incompatible_count": len(incompatible_ids),
        "incompatible_instance_ids": incompatible_ids,
        "candidate_plan_sha256": inputs.invariants["candidate_plan_sha256"],
        "dataset_revision": inputs.invariants["dataset_revision"],
        "dataset_sha256": inputs.invariants["dataset_sha256"],
        "material_package_sha256": inputs.invariants["material_package_sha256"],
        "image_lock_sha256": inputs.invariants["image_lock_sha256"],
        "preflight_module_sha256": invariants["preflight_module_sha256"],
        "preflight_controller_sha256": invariants["preflight_controller_sha256"],
        "docker_backend_sha256": invariants["tooling"]["docker_backend_sha256"],
        "verifier_sha256": invariants["tooling"]["verifier_sha256"],
        "predecessor_terminal_receipt_sha256": PREDECESSOR_TERMINAL_RECEIPT_SHA256,
        "journal_sha256": _sha256_file(journal.path),
        "journal_head_sha256": journal.last_sha256,
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }
    _atomic_write(output_path, dump_canonical_json(manifest))
    return manifest


def dry_run_report(inputs: FrozenInputs, journal_path: Path) -> Mapping[str, Any]:
    expected = [candidate["instance_id"] for _, candidate in _candidate_sequence(inputs.plan)]
    recorded = 0
    compatible = 0
    if journal_path.exists():
        invariants = preflight_invariants(inputs)
        journal = PreflightJournal(journal_path, invariants, expected)
        journal._load()  # noqa: SLF001 - intentional read-only audit path
        audit_journal_bindings(inputs, journal, invariants)
        recorded = len(journal.records)
        compatible = sum(
            bool(row["receipt"]["compatible"]) for row in journal.records.values()
        )
    return {
        "dry_run": True,
        "candidate_count": len(expected),
        "journal_exists": journal_path.exists(),
        "recorded": recorded,
        "compatible": compatible,
        "incompatible": recorded - compatible,
        "remaining": len(expected) - recorded,
        "docker_pulls": 0,
        "docker_runs": 0,
        "test_commands_run": 0,
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    freeze = Path("evaluation/frozen/mini-gibson-v2-sequential-2026-10-17")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, default=freeze / "sequential-plan.json")
    parser.add_argument("--registry", type=Path, default=freeze / "pre-plan-exclusions.json")
    parser.add_argument("--freeze-evidence", type=Path, default=freeze / "freeze-evidence.json")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--material-package", type=Path, required=True)
    parser.add_argument("--image-lock", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    inputs = load_frozen_inputs(
        repo_root=args.repo_root,
        plan_path=args.plan,
        registry_path=args.registry,
        evidence_path=args.freeze_evidence,
        dataset_path=args.dataset,
        material_package_path=args.material_package,
        image_lock_path=args.image_lock,
    )
    if args.dry_run:
        print(json.dumps(dry_run_report(inputs, args.journal), sort_keys=True))
        return 0
    invariants = preflight_invariants(inputs)
    expected_ids = [candidate["instance_id"] for _, candidate in _candidate_sequence(inputs.plan)]
    with PreflightJournal(args.journal, invariants, expected_ids) as journal:
        status = run_pending(
            inputs,
            journal,
            backend=DockerBackend(docker=args.docker),
            image_verifier=lambda entry: verify_local_image(entry, docker=args.docker),
            invariants=invariants,
            limit=args.limit,
        )
        if status["complete"]:
            status["manifest"] = finalize(inputs, journal, args.output, invariants)
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
