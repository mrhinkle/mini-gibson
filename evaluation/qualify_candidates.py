"""Resumable, outcome-blind qualification for the frozen SWE-rebench cohort.

This command is deliberately narrower than a scored evaluator.  It verifies the
committed candidate freeze and exact upstream Parquet bytes, seals qualification
inputs, and calls the networkless Docker verifier exactly once per candidate.
It never imports or opens ``bench/`` and it never observes model outcomes.

The journal is the authority during qualification.  Each completed candidate is
one fsynced JSONL record in a SHA-256 chain.  A valid prior record is terminal:
resume skips it whether it qualified or not, so an operator cannot rerun a bad
result into a good one.  Runnable cohort locks are written atomically only after
all 456 frozen candidates have valid, qualified receipts.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tarfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .candidates import _eligibility
from .cohort import (
    DATASET,
    DATASET_REVISION,
    PARSER_SOURCE_REVISION,
    SUPPORTED_LOG_PARSERS,
    canonical_projection_sha256,
    dump_canonical_json,
    validate_lock,
)
from .docker_backend import DockerBackend
from .freeze_real_cohorts import (
    SOURCE_ROWS,
    SOURCE_SHA256,
    validate_freeze_evidence,
)
from .sequential import (
    canonical_plan_sha256,
    finalize_execution_freeze,
    validate_sequential_plan,
)
from .verify_rebench import (
    QualificationTask,
    VerifierMaterial,
    load_pinned_parser_bytes,
    patch_paths,
    qualify_task,
    verify_receipt,
)


JOURNAL_SCHEMA = "mini-gibson-qualification-journal/v1"
MATERIAL_SCHEMA = "mini-gibson-qualification-materials/v1"
IMAGE_LOCK_SCHEMA = "mini-gibson-qualification-image-lock/v1"
FINAL_SCHEMA = "mini-gibson-qualification-final-manifest/v1"
ZERO_SHA256 = "0" * 64
DATASET_FILE = "data/train-00000-of-00001.parquet"
FROZEN_PLAN_CANONICAL_SHA256 = "961ee3c99b89248316f34dcbf8b30caa32291aebb5b239f8a2523634abbd6427"
FROZEN_PLAN_FILE_SHA256 = "28c92eab536d2bd0cae6dc1596ae4fca245d7ba005caf15d355d6dc22cc3df9e"
FROZEN_REGISTRY_CANONICAL_SHA256 = "e683db581e7db3a773793b08b1edb2e9fc769e15f43ea9e8cd8c0a9c3e47b454"
FROZEN_REGISTRY_FILE_SHA256 = "5660348a58783a6e600db8b5864eec301fddc8c351d39061c8adffb13f01aad8"
FROZEN_EVIDENCE_FILE_SHA256 = "ca1ba1c045a883ef256ee74f45fe21d6a7d24e8962715275d6bb4fc847271210"
DATASET_COLUMNS = (
    "base_commit",
    "image_name",
    "instance_id",
    "language",
    "license",
    "patch",
    "problem_statement",
    "repo",
    "test_patch",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "install_config",
    "meta",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
INSTANCE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MATERIAL_KEYS = {
    "schema_version",
    "source",
    "candidate_plan_sha256",
    "ast_fingerprint_spec",
    "parser_files",
    "tasks",
}
MATERIAL_TASK_KEYS = {
    "instance_id",
    "problem_statement",
    "gold_patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
    "install_config",
    "source_identity",
    "ast_edits",
}
SOURCE_IDENTITY_KEYS = {"merge_commit", "episode_ids"}
AST_EDIT_KEYS = {
    "path",
    "operation",
    "node_type",
    "symbol",
    "before_sha256",
    "after_sha256",
}
IMAGE_LOCK_KEYS = {
    "schema_version",
    "source",
    "candidate_plan_sha256",
    "platform",
    "entries",
}
IMAGE_ENTRY_KEYS = {"instance_id", "image_name", "reference", "digest", "workdir"}
HEADER_KEYS = {
    "schema_version",
    "record_type",
    "sequence",
    "previous_record_sha256",
    "invariants",
    "record_sha256",
}
RECEIPT_RECORD_KEYS = {
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


class QualificationOrchestrationError(ValueError):
    """Qualification state is missing, unsafe, or inconsistent."""


@dataclass(frozen=True)
class FrozenInputs:
    repo_root: Path
    plan_path: Path
    registry_path: Path
    evidence_path: Path
    dataset_path: Path
    material_package_path: Path
    image_lock_path: Path
    plan: Mapping[str, Any]
    registry: Mapping[str, Any]
    evidence: Mapping[str, Any]
    dataset_records: Mapping[str, Mapping[str, Any]]
    materials: Mapping[str, Mapping[str, Any]]
    parser_sources: Mapping[str, bytes]
    images: Mapping[str, Mapping[str, Any]]
    invariants: Mapping[str, Any]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(payload)


def _json_object(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationOrchestrationError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualificationOrchestrationError(f"{path}: expected a JSON object")
    return value


def _strict_object(value: Any, keys: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise QualificationOrchestrationError(f"{path}: expected an object")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        unknown = sorted(set(value) - keys)
        raise QualificationOrchestrationError(
            f"{path}: fields differ (missing={missing}, unknown={unknown})"
        )
    return value


def _safe_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or any(char in value for char in "\0\r\n"):
        raise QualificationOrchestrationError(f"{path}: expected a non-empty single-line string")
    return value


def _sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise QualificationOrchestrationError(f"{path}: expected a lowercase SHA-256")
    return value


def _string_list(value: Any, path: str, *, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (required and not value):
        raise QualificationOrchestrationError(f"{path}: expected a JSON array")
    result = tuple(_safe_string(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(set(result)) != len(result):
        raise QualificationOrchestrationError(f"{path}: duplicate entries")
    return result


def _reject_holdout_paths(repo_root: Path, paths: Iterable[Path]) -> None:
    holdout = (repo_root / "bench").resolve()
    for path in paths:
        resolved = path.resolve()
        if resolved == holdout or holdout in resolved.parents:
            raise QualificationOrchestrationError(
                f"holdout boundary violation: {resolved} is under {holdout}"
            )


def _candidate_sequence(plan: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    return [
        (cohort["cohort_id"], candidate)
        for cohort in plan["cohorts"]
        for candidate in cohort["candidate_report"]["candidates"]
    ]


def _source_binding(value: Any, path: str) -> None:
    source = _strict_object(value, {"dataset", "revision", "split", "file", "sha256", "rows"}, path)
    expected = {
        "dataset": DATASET,
        "revision": DATASET_REVISION,
        "split": "train",
        "file": DATASET_FILE,
        "sha256": SOURCE_SHA256,
        "rows": SOURCE_ROWS,
    }
    if source != expected:
        raise QualificationOrchestrationError(f"{path}: does not bind the exact pinned dataset")


def _iter_pinned_records(path: Path) -> Iterable[Mapping[str, Any]]:
    if _sha256_file(path) != SOURCE_SHA256:
        raise QualificationOrchestrationError("dataset bytes do not match the pinned SHA-256")
    try:
        from pyarrow import parquet  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only by real CLI environment
        raise QualificationOrchestrationError(
            "pyarrow is required to read the pinned qualification Parquet"
        ) from exc
    parquet_file = parquet.ParquetFile(path)
    if parquet_file.metadata.num_rows != SOURCE_ROWS:
        raise QualificationOrchestrationError("dataset row count does not match the pinned source")
    missing = set(DATASET_COLUMNS) - set(parquet_file.schema_arrow.names)
    if missing:
        raise QualificationOrchestrationError(f"dataset is missing qualification columns: {sorted(missing)}")
    for batch in parquet_file.iter_batches(batch_size=64, columns=list(DATASET_COLUMNS)):
        yield from batch.to_pylist()


def _compare_candidate_record(candidate: Mapping[str, Any], record: Mapping[str, Any]) -> None:
    reasons, projection = _eligibility(record)
    if reasons or projection is None:
        raise QualificationOrchestrationError(
            f"{candidate['instance_id']}: pinned dataset row no longer satisfies eligibility: {reasons}"
        )
    shared = {
        "instance_id",
        "repo",
        "base_commit",
        "image_name",
        "language",
        "license",
        "source_pr_url",
        "source_pr_number",
        "source_issue_urls",
        "difficulty",
        "num_modified_files",
        "num_modified_lines",
        "log_parser",
        "install_config_sha256",
        "fingerprints",
    }
    for key in shared:
        if projection[key] != candidate[key]:
            raise QualificationOrchestrationError(
                f"{candidate['instance_id']}: dataset field {key!r} disagrees with frozen plan"
            )


def _load_selected_dataset_records(
    path: Path, plan: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    candidates = {candidate["instance_id"]: candidate for _, candidate in _candidate_sequence(plan)}
    selected: dict[str, Mapping[str, Any]] = {}
    for row in _iter_pinned_records(path):
        instance_id = row.get("instance_id")
        if instance_id not in candidates:
            continue
        if instance_id in selected:
            raise QualificationOrchestrationError(f"duplicate dataset row for {instance_id}")
        _compare_candidate_record(candidates[instance_id], row)
        selected[instance_id] = row
    missing = sorted(set(candidates) - set(selected))
    if missing:
        raise QualificationOrchestrationError(f"pinned dataset lacks frozen candidates: {missing[:5]}")
    return selected


def _validate_ast_edits(value: Any, path: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise QualificationOrchestrationError(f"{path}: must be a non-empty AST edit list")
    result: list[Mapping[str, Any]] = []
    for index, raw in enumerate(value):
        item_path = f"{path}[{index}]"
        item = _strict_object(raw, AST_EDIT_KEYS, item_path)
        edit_path = _safe_string(item["path"], f"{item_path}.path")
        pure = PurePosixPath(edit_path)
        if edit_path.startswith("/") or ".." in pure.parts or pure.as_posix() != edit_path:
            raise QualificationOrchestrationError(f"{item_path}.path: unsafe or noncanonical")
        if item["operation"] not in {"add", "delete", "update", "move"}:
            raise QualificationOrchestrationError(f"{item_path}.operation: unsupported")
        _safe_string(item["node_type"], f"{item_path}.node_type")
        if not isinstance(item["symbol"], str) or any(char in item["symbol"] for char in "\0\r\n"):
            raise QualificationOrchestrationError(f"{item_path}.symbol: malformed")
        for field in ("before_sha256", "after_sha256"):
            digest = item[field]
            if digest is not None:
                _sha256(digest, f"{item_path}.{field}")
        if item["before_sha256"] is None and item["after_sha256"] is None:
            raise QualificationOrchestrationError(f"{item_path}: edit has neither before nor after digest")
        result.append(item)
    canonical = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in result]
    if canonical != sorted(set(canonical)):
        raise QualificationOrchestrationError(f"{path}: AST edits must be unique and canonically ordered")
    return result


def _read_material_package(
    path: Path, plan: Mapping[str, Any], dataset_records: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, Mapping[str, Any]], dict[str, bytes], str]:
    package_sha = _sha256_file(path)
    try:
        archive = tarfile.open(path, mode="r:*")
    except (OSError, tarfile.TarError) as exc:
        raise QualificationOrchestrationError(f"cannot read material package: {exc}") from exc
    with archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise QualificationOrchestrationError("material package contains duplicate members")
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                not member.isfile()
                or member.name.startswith("/")
                or ".." in pure.parts
                or pure.as_posix() != member.name
            ):
                raise QualificationOrchestrationError(
                    f"material package contains unsafe member {member.name!r}"
                )
        if "materials.json" not in names:
            raise QualificationOrchestrationError("material package lacks materials.json")
        extracted = archive.extractfile("materials.json")
        assert extracted is not None
        try:
            manifest = json.loads(extracted.read().decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise QualificationOrchestrationError("material manifest is not valid UTF-8 JSON") from exc
        obj = _strict_object(manifest, MATERIAL_KEYS, "materials")
        if obj["schema_version"] != MATERIAL_SCHEMA:
            raise QualificationOrchestrationError("unsupported material package schema")
        _source_binding(obj["source"], "materials.source")
        plan_sha = canonical_plan_sha256(plan)
        if obj["candidate_plan_sha256"] != plan_sha:
            raise QualificationOrchestrationError("materials do not bind the frozen plan")
        if obj["ast_fingerprint_spec"] != "mini-gibson-ast-edits/v1":
            raise QualificationOrchestrationError("unsupported AST fingerprint specification")
        parser_files = obj["parser_files"]
        if not isinstance(parser_files, dict) or not parser_files:
            raise QualificationOrchestrationError("materials.parser_files must be a non-empty object")
        parser_sources: dict[str, bytes] = {}
        expected_members = {"materials.json"}
        for parser_name, parser_ref in parser_files.items():
            if parser_name not in SUPPORTED_LOG_PARSERS:
                raise QualificationOrchestrationError(f"unsupported parser {parser_name!r}")
            ref = _strict_object(parser_ref, {"path", "sha256"}, f"materials.parser_files.{parser_name}")
            member_name = _safe_string(ref["path"], f"materials.parser_files.{parser_name}.path")
            if member_name != f"parsers/{parser_name}.py":
                raise QualificationOrchestrationError(f"noncanonical parser member for {parser_name}")
            expected_members.add(member_name)
            member = archive.extractfile(member_name)
            if member is None:
                raise QualificationOrchestrationError(f"material package lacks {member_name}")
            source = member.read()
            expected_sha = _sha256(ref["sha256"], f"materials.parser_files.{parser_name}.sha256")
            if _sha256_bytes(source) != expected_sha:
                raise QualificationOrchestrationError(f"parser digest mismatch for {parser_name}")
            # Compilation and direct-definition checks happen before any Docker run.
            load_pinned_parser_bytes(source, parser_name, expected_sha)
            parser_sources[parser_name] = source
        if set(names) != expected_members:
            raise QualificationOrchestrationError(
                f"material package members differ from manifest: {sorted(set(names) ^ expected_members)}"
            )

    rows = obj["tasks"]
    if not isinstance(rows, list):
        raise QualificationOrchestrationError("materials.tasks must be an array")
    sequence = _candidate_sequence(plan)
    expected_ids = [candidate["instance_id"] for _, candidate in sequence]
    if len(rows) != len(expected_ids):
        raise QualificationOrchestrationError("materials must contain exactly all 456 frozen candidates")
    materials: dict[str, Mapping[str, Any]] = {}
    for index, (raw, expected_id) in enumerate(zip(rows, expected_ids)):
        task = _strict_object(raw, MATERIAL_TASK_KEYS, f"materials.tasks[{index}]")
        instance_id = _safe_string(task["instance_id"], f"materials.tasks[{index}].instance_id")
        if instance_id != expected_id:
            raise QualificationOrchestrationError("material tasks must match frozen order exactly")
        record = dataset_records[instance_id]
        comparisons = {
            "problem_statement": "problem_statement",
            "gold_patch": "patch",
            "test_patch": "test_patch",
            "fail_to_pass": "FAIL_TO_PASS",
            "pass_to_pass": "PASS_TO_PASS",
            "install_config": "install_config",
        }
        for material_key, dataset_key in comparisons.items():
            if task[material_key] != record.get(dataset_key):
                raise QualificationOrchestrationError(
                    f"{instance_id}: material {material_key} disagrees with pinned dataset"
                )
        _string_list(task["fail_to_pass"], f"materials.tasks[{index}].fail_to_pass", required=True)
        _string_list(task["pass_to_pass"], f"materials.tasks[{index}].pass_to_pass")
        identity = _strict_object(
            task["source_identity"], SOURCE_IDENTITY_KEYS, f"materials.tasks[{index}].source_identity"
        )
        if not isinstance(identity["merge_commit"], str) or not GIT_SHA_RE.fullmatch(identity["merge_commit"]):
            raise QualificationOrchestrationError(f"{instance_id}: invalid merge commit")
        _string_list(identity["episode_ids"], f"materials.tasks[{index}].source_identity.episode_ids")
        _validate_ast_edits(task["ast_edits"], f"materials.tasks[{index}].ast_edits")
        product_paths = patch_paths(task["gold_patch"])
        ast_paths = {edit["path"] for edit in task["ast_edits"]}
        if ast_paths != product_paths:
            raise QualificationOrchestrationError(
                f"{instance_id}: AST edit paths do not exactly cover product patch paths"
            )
        install = task["install_config"]
        if not isinstance(install, dict):
            raise QualificationOrchestrationError(f"{instance_id}: install_config must be an object")
        parser_name = install.get("log_parser")
        if parser_name not in parser_sources:
            raise QualificationOrchestrationError(f"{instance_id}: parser source is not sealed")
        materials[instance_id] = task
    used_parsers = {task["install_config"]["log_parser"] for task in materials.values()}
    if used_parsers != set(parser_sources):
        raise QualificationOrchestrationError("material package must contain exactly the used parser sources")
    return materials, parser_sources, package_sha


def _image_repository(image_name: str) -> str:
    slash = image_name.rfind("/")
    colon = image_name.rfind(":")
    return image_name[:colon] if colon > slash else image_name


def _read_image_lock(path: Path, plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    obj = _strict_object(_json_object(path), IMAGE_LOCK_KEYS, "image_lock")
    if obj["schema_version"] != IMAGE_LOCK_SCHEMA:
        raise QualificationOrchestrationError("unsupported image lock schema")
    _source_binding(obj["source"], "image_lock.source")
    if obj["candidate_plan_sha256"] != canonical_plan_sha256(plan):
        raise QualificationOrchestrationError("image lock does not bind the frozen plan")
    if obj["platform"] != "linux/amd64":
        raise QualificationOrchestrationError("image lock platform must be linux/amd64")
    entries = obj["entries"]
    sequence = _candidate_sequence(plan)
    if not isinstance(entries, list) or len(entries) != len(sequence):
        raise QualificationOrchestrationError("image lock must contain exactly all 456 candidates")
    result: dict[str, Mapping[str, Any]] = {}
    for index, (raw, (_, candidate)) in enumerate(zip(entries, sequence)):
        entry = _strict_object(raw, IMAGE_ENTRY_KEYS, f"image_lock.entries[{index}]")
        instance_id = _safe_string(entry["instance_id"], f"image_lock.entries[{index}].instance_id")
        if instance_id != candidate["instance_id"] or entry["image_name"] != candidate["image_name"]:
            raise QualificationOrchestrationError("image lock entries must match frozen order and tags")
        digest = entry["digest"]
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise QualificationOrchestrationError(f"{instance_id}: invalid immutable image digest")
        reference = entry["reference"]
        if reference != f"{_image_repository(candidate['image_name'])}@{digest}":
            raise QualificationOrchestrationError(f"{instance_id}: image reference/tag/digest mismatch")
        workdir = entry["workdir"]
        pure = PurePosixPath(workdir) if isinstance(workdir, str) else PurePosixPath(".")
        if not isinstance(workdir, str) or not workdir.startswith("/") or workdir == "/" or ".." in pure.parts:
            raise QualificationOrchestrationError(f"{instance_id}: unsafe image workdir")
        if instance_id in result:
            raise QualificationOrchestrationError(f"duplicate image lock entry for {instance_id}")
        result[instance_id] = entry
    return result


def verify_local_image(entry: Mapping[str, Any], *, docker: str = "docker") -> None:
    """Resolve a locked digest against local Docker metadata without pulling."""

    try:
        completed = subprocess.run(
            [docker, "image", "inspect", entry["reference"]],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QualificationOrchestrationError(f"Docker image inspection failed: {exc}") from exc
    if completed.returncode != 0:
        raise QualificationOrchestrationError(
            f"immutable image is not locally available: {entry['reference']}"
        )
    try:
        values = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise QualificationOrchestrationError("Docker image inspect returned invalid JSON") from exc
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise QualificationOrchestrationError("Docker image inspect returned an ambiguous result")
    metadata = values[0]
    repo_digests = metadata.get("RepoDigests")
    if (
        not isinstance(repo_digests, list)
        or entry["reference"] not in repo_digests
        or metadata.get("Os") != "linux"
        or metadata.get("Architecture") != "amd64"
        or not isinstance(metadata.get("Config"), dict)
        or metadata["Config"].get("WorkingDir") != entry["workdir"]
    ):
        raise QualificationOrchestrationError(
            "local image metadata does not match the locked digest/platform/workdir"
        )


def load_frozen_inputs(
    *,
    repo_root: Path,
    plan_path: Path,
    registry_path: Path,
    evidence_path: Path,
    dataset_path: Path,
    material_package_path: Path,
    image_lock_path: Path,
) -> FrozenInputs:
    code_root = Path(__file__).resolve().parents[1]
    if repo_root.resolve() != code_root:
        raise QualificationOrchestrationError(
            f"repo_root must be the checkout containing this orchestrator: {code_root}"
        )
    paths = (
        plan_path,
        registry_path,
        evidence_path,
        dataset_path,
        material_package_path,
        image_lock_path,
    )
    _reject_holdout_paths(repo_root, paths)
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise QualificationOrchestrationError(
                f"qualification input must be a regular non-symlink file: {path}"
            )
    plan = _json_object(plan_path)
    registry = _json_object(registry_path)
    evidence = _json_object(evidence_path)
    validate_sequential_plan(plan)
    validate_freeze_evidence(evidence, registry, plan)
    authority_hashes = {
        "plan canonical": (canonical_plan_sha256(plan), FROZEN_PLAN_CANONICAL_SHA256),
        "plan file": (_sha256_file(plan_path), FROZEN_PLAN_FILE_SHA256),
        "registry canonical": (_canonical_sha256(registry), FROZEN_REGISTRY_CANONICAL_SHA256),
        "registry file": (_sha256_file(registry_path), FROZEN_REGISTRY_FILE_SHA256),
        "freeze evidence file": (_sha256_file(evidence_path), FROZEN_EVIDENCE_FILE_SHA256),
    }
    for name, (actual, expected) in authority_hashes.items():
        if actual != expected:
            raise QualificationOrchestrationError(
                f"frozen {name} SHA-256 mismatch: expected {expected}, got {actual}"
            )
    dataset_records = _load_selected_dataset_records(dataset_path, plan)
    materials, parser_sources, package_sha = _read_material_package(
        material_package_path, plan, dataset_records
    )
    images = _read_image_lock(image_lock_path, plan)
    repo_files = {
        "orchestrator_sha256": _sha256_file(Path(__file__)),
        "docker_backend_sha256": _sha256_file(repo_root / "evaluation/docker_backend.py"),
        "verifier_sha256": _sha256_file(repo_root / "evaluation/verify_rebench.py"),
        "cohort_validator_sha256": _sha256_file(repo_root / "evaluation/cohort.py"),
    }
    invariants = {
        "candidate_plan_sha256": canonical_plan_sha256(plan),
        "candidate_plan_file_sha256": _sha256_file(plan_path),
        "base_exclusion_registry_canonical_sha256": _canonical_sha256(registry),
        "base_exclusion_registry_file_sha256": _sha256_file(registry_path),
        "freeze_evidence_file_sha256": _sha256_file(evidence_path),
        "dataset_revision": DATASET_REVISION,
        "dataset_sha256": SOURCE_SHA256,
        "material_package_sha256": package_sha,
        "image_lock_sha256": _sha256_file(image_lock_path),
        "parser_source_sha256": {
            name: _sha256_bytes(source) for name, source in sorted(parser_sources.items())
        },
        "verifier_package_sha256": package_sha,
        "tooling": repo_files,
        "ordered_instance_ids_sha256": _canonical_sha256(
            [candidate["instance_id"] for _, candidate in _candidate_sequence(plan)]
        ),
        "candidate_count": 456,
        "final_holdout_status": "sealed_not_read_or_run",
    }
    return FrozenInputs(
        repo_root=repo_root,
        plan_path=plan_path,
        registry_path=registry_path,
        evidence_path=evidence_path,
        dataset_path=dataset_path,
        material_package_path=material_package_path,
        image_lock_path=image_lock_path,
        plan=plan,
        registry=registry,
        evidence=evidence,
        dataset_records=dataset_records,
        materials=materials,
        parser_sources=parser_sources,
        images=images,
        invariants=invariants,
    )


def _record_hash(record: Mapping[str, Any]) -> str:
    body = dict(record)
    body.pop("record_sha256", None)
    return _canonical_sha256(body)


class HashChainJournal:
    """Exclusive append-only journal with a strict receipt hash chain."""

    def __init__(self, path: Path, invariants: Mapping[str, Any], expected_ids: Sequence[str]) -> None:
        self.path = path
        self.invariants = invariants
        self.expected_ids = tuple(expected_ids)
        self._lock_handle: BinaryIO | None = None
        self.records: dict[str, Mapping[str, Any]] = {}
        self.last_sha256 = ZERO_SHA256
        self.next_sequence = 0

    def __enter__(self) -> HashChainJournal:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise QualificationOrchestrationError("qualification journal cannot be a symlink")
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        if lock_path.is_symlink():
            raise QualificationOrchestrationError("qualification journal lock cannot be a symlink")
        self._lock_handle = lock_path.open("a+b")
        fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self._load_or_initialize()
        return self

    def __exit__(self, *_args: object) -> None:
        if self._lock_handle is not None:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None

    def _load_or_initialize(self) -> None:
        if not self.path.exists():
            header = {
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
            raw_lines = self.path.read_bytes().splitlines(keepends=True)
        except OSError as exc:
            raise QualificationOrchestrationError(f"cannot read journal: {exc}") from exc
        if not raw_lines or any(not line.endswith(b"\n") for line in raw_lines):
            raise QualificationOrchestrationError("journal is empty or has an incomplete final record")
        for sequence, line in enumerate(raw_lines):
            try:
                record = json.loads(line)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise QualificationOrchestrationError(f"journal record {sequence} is invalid JSON") from exc
            if not isinstance(record, dict):
                raise QualificationOrchestrationError(f"journal record {sequence} is not an object")
            expected_keys = HEADER_KEYS if sequence == 0 else RECEIPT_RECORD_KEYS
            _strict_object(record, expected_keys, f"journal[{sequence}]")
            if (
                record["schema_version"] != JOURNAL_SCHEMA
                or record["sequence"] != sequence
                or record["previous_record_sha256"] != previous
                or record["record_sha256"] != _record_hash(record)
            ):
                raise QualificationOrchestrationError(f"journal record {sequence} breaks the hash chain")
            if sequence == 0:
                if record["record_type"] != "header" or record["invariants"] != self.invariants:
                    raise QualificationOrchestrationError("journal header invariants do not match this run")
            else:
                if record["record_type"] != "qualification_receipt":
                    raise QualificationOrchestrationError(f"journal record {sequence} has wrong type")
                instance_id = record["instance_id"]
                if instance_id not in self.expected_ids:
                    raise QualificationOrchestrationError(f"journal contains unplanned task {instance_id!r}")
                if sequence > len(self.expected_ids):
                    raise QualificationOrchestrationError("journal has more records than frozen candidates")
                if instance_id != self.expected_ids[sequence - 1]:
                    raise QualificationOrchestrationError(
                        f"journal record {sequence} is out of frozen candidate order"
                    )
                if instance_id in self.records:
                    raise QualificationOrchestrationError(f"journal contains duplicate task {instance_id!r}")
                if not verify_receipt(record["receipt"]):
                    raise QualificationOrchestrationError(f"journal receipt for {instance_id} is incomplete")
                if record["receipt"]["instance_id"] != instance_id:
                    raise QualificationOrchestrationError(f"journal receipt/task mismatch for {instance_id}")
                self.records[instance_id] = record
            previous = record["record_sha256"]
        self.last_sha256 = previous
        self.next_sequence = len(raw_lines)

    def _append_bytes(self, payload: bytes) -> None:
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        descriptor = os.open(self.path, flags, 0o600)
        try:
            written = os.write(descriptor, payload)
            if written != len(payload):
                raise QualificationOrchestrationError("short append to qualification journal")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

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
            raise QualificationOrchestrationError(f"refusing to reclassify prior task {instance_id}")
        if self.next_sequence > len(self.expected_ids) or instance_id != self.expected_ids[self.next_sequence - 1]:
            raise QualificationOrchestrationError("refusing an out-of-order qualification receipt")
        if not verify_receipt(receipt) or receipt["instance_id"] != instance_id:
            raise QualificationOrchestrationError(f"refusing incomplete receipt for {instance_id}")
        record: dict[str, Any] = {
            "schema_version": JOURNAL_SCHEMA,
            "record_type": "qualification_receipt",
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
        # Re-read the complete journal after every append.  This is slower than
        # trusting process memory, but qualification runs dominate runtime and
        # the check detects disk corruption at the evidence boundary.
        self._load()


def _task_input_sha256(
    candidate: Mapping[str, Any], material: Mapping[str, Any], image: Mapping[str, Any], parser_sha: str
) -> str:
    return _canonical_sha256(
        {
            "candidate": candidate,
            "material_sha256": _canonical_sha256(material),
            "image": image,
            "parser_sha256": parser_sha,
            "verify_timeout_s": 900,
        }
    )


def _validate_prior_record_binding(
    inputs: FrozenInputs,
    cohort_id: str,
    candidate: Mapping[str, Any],
    record: Mapping[str, Any],
) -> None:
    instance_id = candidate["instance_id"]
    material = inputs.materials[instance_id]
    image = inputs.images[instance_id]
    install = material["install_config"]
    parser_name = install["log_parser"]
    parser_sha = _sha256_bytes(inputs.parser_sources[parser_name])
    expected_input = _task_input_sha256(candidate, material, image, parser_sha)
    receipt = record["receipt"]
    expected_receipt_fields = {
        "instance_id": instance_id,
        "image_reference": image["reference"],
        "image_digest": image["digest"],
        "workdir": image["workdir"],
        "verify_timeout_s": 900,
        "parser_name": parser_name,
        "parser_sha256": parser_sha,
        "gold_patch_sha256": _sha256_bytes(material["gold_patch"].encode()),
        "test_patch_sha256": _sha256_bytes(material["test_patch"].encode()),
        "test_command_sha256": _sha256_bytes(install["test_cmd"].encode()),
    }
    if (
        record["cohort_id"] != cohort_id
        or record["selection_rank"] != candidate["selection_rank"]
        or record["input_sha256"] != expected_input
    ):
        raise QualificationOrchestrationError(f"prior journal binding disagrees for {instance_id}")
    for field, expected in expected_receipt_fields.items():
        if receipt[field] != expected:
            raise QualificationOrchestrationError(
                f"prior receipt field {field!r} disagrees for {instance_id}"
            )


def audit_journal_bindings(inputs: FrozenInputs, journal: HashChainJournal) -> None:
    for cohort_id, candidate in _candidate_sequence(inputs.plan):
        record = journal.records.get(candidate["instance_id"])
        if record is not None:
            _validate_prior_record_binding(inputs, cohort_id, candidate, record)


def _qualify_one(
    inputs: FrozenInputs,
    candidate: Mapping[str, Any],
    *,
    backend: DockerBackend,
    image_verifier: Callable[[Mapping[str, Any]], None],
) -> tuple[dict[str, Any], str]:
    instance_id = candidate["instance_id"]
    material = inputs.materials[instance_id]
    image = inputs.images[instance_id]
    image_verifier(image)
    install = material["install_config"]
    parser_name = install["log_parser"]
    parser_source = inputs.parser_sources[parser_name]
    parser_sha = _sha256_bytes(parser_source)
    parser = load_pinned_parser_bytes(parser_source, parser_name, parser_sha)
    verifier_material = VerifierMaterial(
        gold_patch=material["gold_patch"],
        test_patch=material["test_patch"],
        fail_to_pass=tuple(material["fail_to_pass"]),
        pass_to_pass=tuple(material["pass_to_pass"]),
        test_command=install["test_cmd"],
        parser_name=parser_name,
        parser_sha256=parser_sha,
    )
    receipt = qualify_task(
        QualificationTask(
            instance_id=instance_id,
            image_reference=image["reference"],
            image_digest=image["digest"],
            workdir=image["workdir"],
            verify_timeout_s=900,
        ),
        verifier_material,
        parser=parser,
        backend=backend,
    )
    return receipt, _task_input_sha256(candidate, material, image, parser_sha)


def run_pending(
    inputs: FrozenInputs,
    journal: HashChainJournal,
    *,
    backend: DockerBackend,
    image_verifier: Callable[[Mapping[str, Any]], None],
    limit: int | None = None,
) -> dict[str, Any]:
    audit_journal_bindings(inputs, journal)
    prior_unqualified = [
        instance_id
        for instance_id, record in journal.records.items()
        if not record["receipt"]["qualified"]
    ]
    if prior_unqualified:
        return {
            "processed_this_invocation": 0,
            "recorded": len(journal.records),
            "qualified": len(journal.records) - len(prior_unqualified),
            "remaining": 456 - len(journal.records),
            "terminal_failure": prior_unqualified[0],
            "complete": False,
            "journal_head_sha256": journal.last_sha256,
        }
    processed = 0
    terminal_failure: str | None = None
    for cohort_id, candidate in _candidate_sequence(inputs.plan):
        instance_id = candidate["instance_id"]
        if instance_id in journal.records:
            continue
        if limit is not None and processed >= limit:
            break
        receipt, input_sha = _qualify_one(
            inputs, candidate, backend=backend, image_verifier=image_verifier
        )
        journal.append(
            cohort_id=cohort_id,
            selection_rank=candidate["selection_rank"],
            instance_id=instance_id,
            input_sha256=input_sha,
            receipt=receipt,
        )
        processed += 1
        if not receipt["qualified"]:
            terminal_failure = instance_id
            break
    qualified = sum(bool(row["receipt"]["qualified"]) for row in journal.records.values())
    return {
        "processed_this_invocation": processed,
        "recorded": len(journal.records),
        "qualified": qualified,
        "remaining": 456 - len(journal.records),
        "terminal_failure": terminal_failure,
        "complete": len(journal.records) == 456 and qualified == 456,
        "journal_head_sha256": journal.last_sha256,
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise QualificationOrchestrationError(f"final artifact cannot be a symlink: {path}")
    if path.exists():
        if path.read_bytes() != payload:
            raise QualificationOrchestrationError(f"refusing to overwrite differing final artifact {path}")
        return
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if os.write(descriptor, payload) != len(payload):
            raise QualificationOrchestrationError(f"short write for {path}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _build_lock(
    inputs: FrozenInputs, cohort: Mapping[str, Any], journal: HashChainJournal
) -> dict[str, Any]:
    candidate_report = cohort["candidate_report"]
    tasks = []
    for candidate in candidate_report["candidates"]:
        instance_id = candidate["instance_id"]
        material = inputs.materials[instance_id]
        image = inputs.images[instance_id]
        receipt = journal.records[instance_id]["receipt"]
        install = material["install_config"]
        task = {
            "selection_rank": candidate["selection_rank"],
            "instance_id": instance_id,
            "repo": candidate["repo"],
            "source_identity": {
                "pr_url": candidate["source_pr_url"],
                "pr_number": candidate["source_pr_number"],
                "issue_urls": candidate["source_issue_urls"],
                "merge_commit": material["source_identity"]["merge_commit"],
                "episode_ids": material["source_identity"]["episode_ids"],
            },
            "base_commit": candidate["base_commit"],
            "problem_statement": material["problem_statement"],
            "language": candidate["language"],
            "license": candidate["license"],
            "split": cohort["mode"],
            "image": {
                "reference": image["reference"],
                "digest": image["digest"],
                "platform": "linux/amd64",
                "workdir": image["workdir"],
            },
            "install_config_sha256": candidate["install_config_sha256"],
            "task_projection_sha256": "",
            "fingerprints": {
                **candidate["fingerprints"],
                "ast_edits_sha256": _canonical_sha256(material["ast_edits"]),
            },
            "qualification": {
                "status": "qualified",
                "receipt_sha256": receipt["receipt_sha256"],
                "base_fail_repeats": receipt["base_fail_repeats"],
                "gold_pass_repeats": receipt["gold_pass_repeats"],
            },
            "log_parser": install["log_parser"],
            "verify_timeout_s": 900,
        }
        task["task_projection_sha256"] = canonical_projection_sha256(task)
        tasks.append(task)
    mode = cohort["mode"]
    lock = {
        "schema_version": "mini-gibson-real-repo-cohort/v1",
        "cohort_id": cohort["cohort_id"],
        "mode": mode,
        "source": {
            "dataset": DATASET,
            "revision": DATASET_REVISION,
            "split": "train",
            "dataset_card_url": f"https://huggingface.co/datasets/{DATASET}/tree/{DATASET_REVISION}",
        },
        "selection": {
            "policy_version": candidate_report["selection"]["policy_version"],
            "seed": cohort["seed"],
            "expected_tasks": 24 if mode == "pilot" else 144,
            "min_languages": 6 if mode == "pilot" else 8,
            "min_repositories": 12 if mode == "pilot" else 24,
            "max_tasks_per_repo": 4 if mode == "pilot" else 8,
        },
        "exclusion_registry": {
            "path": inputs.registry_path.name,
            "sha256": _sha256_file(inputs.registry_path),
        },
        "sealed_verifier_package": {
            "path": inputs.material_package_path.name,
            "sha256": inputs.invariants["material_package_sha256"],
        },
        "parser": {
            "source_repo": "https://github.com/SWE-rebench/SWE-rebench-V2",
            "source_revision": PARSER_SOURCE_REVISION,
            "vendored_parser_sha256": _canonical_sha256(inputs.invariants["parser_source_sha256"]),
        },
        "tasks": tasks,
    }
    validate_lock(lock, inputs.registry)
    return lock


def finalize(inputs: FrozenInputs, journal: HashChainJournal, output_dir: Path) -> Mapping[str, Any]:
    audit_journal_bindings(inputs, journal)
    expected = [candidate["instance_id"] for _, candidate in _candidate_sequence(inputs.plan)]
    if set(journal.records) != set(expected):
        raise QualificationOrchestrationError("cannot finalize before every frozen candidate has a receipt")
    unqualified = [
        instance_id
        for instance_id, record in journal.records.items()
        if not record["receipt"]["qualified"]
    ]
    if unqualified:
        raise QualificationOrchestrationError(
            f"cannot finalize with unqualified terminal receipts: {unqualified[:5]}"
        )
    locks = {
        cohort["cohort_id"]: _build_lock(inputs, cohort, journal)
        for cohort in inputs.plan["cohorts"]
    }
    execution_freeze, training_registry = finalize_execution_freeze(
        inputs.plan, inputs.registry, locks
    )
    lock_files = {cohort_id: f"qualified-lock-{cohort_id}.json" for cohort_id in locks}
    final_manifest = {
        "schema_version": FINAL_SCHEMA,
        "status": "qualification_complete_runnable",
        "candidate_plan_sha256": canonical_plan_sha256(inputs.plan),
        "dataset_revision": DATASET_REVISION,
        "dataset_sha256": SOURCE_SHA256,
        "material_package_sha256": inputs.invariants["material_package_sha256"],
        "image_lock_sha256": inputs.invariants["image_lock_sha256"],
        "parser_source_sha256": inputs.invariants["parser_source_sha256"],
        "tooling": inputs.invariants["tooling"],
        "journal_head_sha256": journal.last_sha256,
        "qualification_receipts": 456,
        "qualified_receipts": 456,
        "qualified_locks": {
            cohort_id: {
                "path": lock_files[cohort_id],
                "canonical_sha256": _canonical_sha256(lock),
            }
            for cohort_id, lock in locks.items()
        },
        "training_exclusion_registry": {
            "path": "training-exclusion-registry.json",
            "canonical_sha256": _canonical_sha256(training_registry),
        },
        "execution_freeze": {
            "path": "execution-freeze.json",
            "canonical_sha256": _canonical_sha256(execution_freeze),
        },
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }
    for cohort_id, lock in locks.items():
        _atomic_write(output_dir / lock_files[cohort_id], dump_canonical_json(lock))
    _atomic_write(
        output_dir / "training-exclusion-registry.json", dump_canonical_json(training_registry)
    )
    _atomic_write(output_dir / "execution-freeze.json", dump_canonical_json(execution_freeze))
    _atomic_write(output_dir / "qualification-final-manifest.json", dump_canonical_json(final_manifest))
    return final_manifest


def dry_run_report(inputs: FrozenInputs, journal_path: Path) -> Mapping[str, Any]:
    expected_ids = [candidate["instance_id"] for _, candidate in _candidate_sequence(inputs.plan)]
    blockers = [
        {
            "code": "docker_images_not_verified",
            "count": 456,
            "detail": "dry-run never calls Docker; immutable local digests are verified immediately before execution",
        }
    ]
    recorded = 0
    qualified = 0
    if journal_path.exists():
        # Read-only validation: copy the loader logic without creating a header.
        journal = HashChainJournal(journal_path, inputs.invariants, expected_ids)
        journal._load()  # noqa: SLF001 - intentional read-only audit path
        audit_journal_bindings(inputs, journal)
        recorded = len(journal.records)
        qualified = sum(bool(row["receipt"]["qualified"]) for row in journal.records.values())
        if recorded != qualified:
            blockers.append(
                {
                    "code": "terminal_unqualified_receipt",
                    "count": recorded - qualified,
                    "detail": "prior qualification failures cannot be reclassified",
                }
            )
    return {
        "dry_run": True,
        "ready_to_attempt": recorded == qualified,
        "candidate_count": 456,
        "recorded": recorded,
        "qualified": qualified,
        "remaining": 456 - recorded,
        "blockers": blockers,
        "docker_pulls": 0,
        "docker_runs": 0,
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
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise QualificationOrchestrationError("--limit must be positive")
    repo_root = args.repo_root.resolve()
    inputs = load_frozen_inputs(
        repo_root=repo_root,
        plan_path=(repo_root / args.plan).resolve() if not args.plan.is_absolute() else args.plan.resolve(),
        registry_path=(repo_root / args.registry).resolve()
        if not args.registry.is_absolute()
        else args.registry.resolve(),
        evidence_path=(repo_root / args.freeze_evidence).resolve()
        if not args.freeze_evidence.is_absolute()
        else args.freeze_evidence.resolve(),
        dataset_path=args.dataset.resolve(),
        material_package_path=args.material_package.resolve(),
        image_lock_path=args.image_lock.resolve(),
    )
    _reject_holdout_paths(repo_root, (args.journal, args.output_dir))
    if args.dry_run:
        report = dry_run_report(inputs, args.journal.resolve())
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    expected_ids = [candidate["instance_id"] for _, candidate in _candidate_sequence(inputs.plan)]
    with HashChainJournal(args.journal.resolve(), inputs.invariants, expected_ids) as journal:
        backend = DockerBackend(docker=args.docker)
        status = run_pending(
            inputs,
            journal,
            backend=backend,
            image_verifier=lambda entry: verify_local_image(entry, docker=args.docker),
            limit=args.limit,
        )
        if status["complete"]:
            status["final_manifest"] = finalize(inputs, journal, args.output_dir.resolve())
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0 if status["terminal_failure"] is None else 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
