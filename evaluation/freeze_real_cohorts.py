"""Freeze the real SWE-rebench V2 pilot and development candidate manifests.

The command reads only the outcome-blind columns needed by the merged
eligibility policy.  It never emits problem statements, patches, test patches,
declared tests, model outcomes, or runnable qualification material.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .candidates import CandidateSelectionError
from .cohort import DATASET, DATASET_REVISION, validate_registry
from .sequential import (
    canonical_plan_sha256,
    freeze_sequential_plan,
    validate_sequential_plan,
)

SOURCE_FILE = "data/train-00000-of-00001.parquet"
SOURCE_SHA256 = "0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad"
SOURCE_ROWS = 32_079
PLAN_ID = "mini-gibson-v2-sequential-2026-10-17"
MASTER_SEED = 414
FREEZE_SCHEMA = "mini-gibson-real-cohort-freeze-evidence/v1"

PARQUET_COLUMNS = (
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
    "install_config",
    "meta",
)

OBSERVATIONAL_MANIFEST = Path("training/dataset/observational/tasks.manifest.json")
V1_TRAINING_MANIFEST = Path(
    "docs/evidence/lightning-openhands-2026-10-17/training/training-data-manifest.json"
)
PRIOR_DEVELOPMENT_FIXTURES = Path(
    "docs/evidence/lightning-openhands-2026-10-17/fixtures"
)


class RealCohortFreezeError(ValueError):
    """The pinned source or pre-outcome freeze evidence is inconsistent."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _json_file_sha256(value: Any) -> str:
    return hashlib.sha256(_render_json(value)).hexdigest()


def _render_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _load_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RealCohortFreezeError(f"{path}: expected a JSON object")
    return value


def build_base_exclusion_registry(repo_root: Path) -> dict[str, Any]:
    """Build the pre-plan registry without opening final-holdout task bytes."""

    observational_path = repo_root / OBSERVATIONAL_MANIFEST
    training_path = repo_root / V1_TRAINING_MANIFEST
    fixture_root = repo_root / PRIOR_DEVELOPMENT_FIXTURES
    observational = _load_object(observational_path)
    training = _load_object(training_path)
    fixture_ids = sorted(path.name for path in fixture_root.iterdir() if path.is_dir())

    sources = [
        {
            "name": "v1-openhands-training-and-sealed-repo-boundary",
            "sha256": _sha256_file(training_path),
        },
        {
            "name": "observational-task-manifest",
            "sha256": _sha256_file(observational_path),
        },
        {
            "name": "prior-development-fixture-identities",
            "sha256": _canonical_sha256(fixture_ids),
        },
    ]
    entries: dict[tuple[str, str], dict[str, str]] = {}

    def add(kind: str, value: Any, source: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise RealCohortFreezeError(f"invalid {kind} exclusion from {source}")
        normalized = value.strip().casefold() if kind == "repo" else value.strip()
        entries.setdefault(
            (kind, normalized.casefold()),
            {"kind": kind, "value": normalized, "source": source},
        )

    v1_source = sources[0]["name"]
    blocked_repos = training.get("blocked_repos")
    selected = training.get("selected")
    if not isinstance(blocked_repos, list) or not isinstance(selected, list):
        raise RealCohortFreezeError(
            "v1 training manifest lacks blocked_repos or selected"
        )
    for repo in blocked_repos:
        add("repo", repo, v1_source)
    for index, raw in enumerate(selected):
        if not isinstance(raw, dict):
            raise RealCohortFreezeError(
                f"v1 training selected[{index}] is not an object"
            )
        add("instance_id", raw.get("instance_id"), v1_source)
        add("repo", raw.get("repo"), v1_source)
        add("episode_id", raw.get("trajectory_id"), v1_source)

    obs_source = sources[1]["name"]
    tasks = observational.get("tasks")
    if not isinstance(tasks, list):
        raise RealCohortFreezeError("observational manifest lacks tasks")
    for index, raw in enumerate(tasks):
        if not isinstance(raw, dict):
            raise RealCohortFreezeError(
                f"observational tasks[{index}] is not an object"
            )
        add("instance_id", raw.get("task_id"), obs_source)

    fixture_source = sources[2]["name"]
    for fixture_id in fixture_ids:
        add("instance_id", fixture_id, fixture_source)

    registry = {
        "schema_version": "mini-gibson-exclusion-registry/v1",
        "registry_id": "mini-gibson-v2-pre-plan-exclusions-2026-10-17",
        "source_digests": sources,
        "entries": sorted(
            entries.values(), key=lambda row: (row["kind"], row["value"])
        ),
    }
    validate_registry(registry)
    return registry


def iter_pinned_parquet(path: Path) -> Iterable[Mapping[str, Any]]:
    """Yield only policy-required columns from the exact pinned Parquet bytes."""

    source_digest = _sha256_file(path)
    if source_digest != SOURCE_SHA256:
        raise RealCohortFreezeError(
            f"source SHA-256 mismatch: expected {SOURCE_SHA256}, got {source_digest}"
        )
    try:
        from pyarrow import parquet  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - real CLI environment only
        raise RealCohortFreezeError(
            "pyarrow is required only for pinned Parquet regeneration"
        ) from exc

    parquet_file = parquet.ParquetFile(path)
    if parquet_file.metadata.num_rows != SOURCE_ROWS:
        raise RealCohortFreezeError(
            f"source row count mismatch: expected {SOURCE_ROWS}, "
            f"got {parquet_file.metadata.num_rows}"
        )
    missing = set(PARQUET_COLUMNS) - set(parquet_file.schema_arrow.names)
    if missing:
        raise RealCohortFreezeError(
            f"source is missing required columns: {sorted(missing)}"
        )
    for batch in parquet_file.iter_batches(
        batch_size=64, columns=list(PARQUET_COLUMNS)
    ):
        yield from batch.to_pylist()


def _candidate_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    cohorts = plan["cohorts"]
    candidates = [
        candidate
        for cohort in cohorts
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    development = [
        candidate
        for cohort in cohorts
        if cohort["mode"] == "development"
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    return {
        "cohort_sizes": {
            cohort["cohort_id"]: len(cohort["candidate_report"]["candidates"])
            for cohort in cohorts
        },
        "total_candidates": len(candidates),
        "development_candidates": len(development),
        "unique_instance_ids": len({row["instance_id"] for row in candidates}),
        "unique_fingerprint_sets": {
            name: len({row["fingerprints"][name] for row in candidates})
            for name in (
                "issue_text_sha256",
                "patch_sha256",
                "test_patch_sha256",
                "changed_files_sha256",
                "image_cluster_sha256",
            )
        },
        "unique_image_clusters": len(
            {row["fingerprints"]["image_cluster_sha256"] for row in candidates}
        ),
        "log_parsers": sorted({row["log_parser"] for row in candidates}),
    }


def build_freeze_evidence(
    *,
    repo_root: Path,
    source_path: Path,
    registry: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a deterministic receipt for the non-runnable candidate freeze."""

    registry_bytes = _render_json(registry)
    plan_bytes = _render_json(plan)
    return {
        "schema_version": FREEZE_SCHEMA,
        "plan_id": PLAN_ID,
        "frozen_on": "2026-10-17",
        "source": {
            "dataset": DATASET,
            "revision": DATASET_REVISION,
            "split": "train",
            "file": SOURCE_FILE,
            "sha256": _sha256_file(source_path),
            "rows": SOURCE_ROWS,
            "columns_read": list(PARQUET_COLUMNS),
            "model_outcome_columns_read": [],
        },
        "artifacts": {
            "base_exclusion_registry": {
                "path": "pre-plan-exclusions.json",
                "file_sha256": hashlib.sha256(registry_bytes).hexdigest(),
                "canonical_sha256": _canonical_sha256(registry),
            },
            "sequential_plan": {
                "path": "sequential-plan.json",
                "file_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                "canonical_sha256": canonical_plan_sha256(plan),
            },
        },
        "tooling": {
            "candidate_selector_sha256": _sha256_file(
                repo_root / "evaluation/candidates.py"
            ),
            "cohort_validator_sha256": _sha256_file(repo_root / "evaluation/cohort.py"),
            "freeze_generator_sha256": _sha256_file(
                repo_root / "evaluation/freeze_real_cohorts.py"
            ),
            "sequential_freezer_sha256": _sha256_file(
                repo_root / "evaluation/sequential.py"
            ),
            "evidence_schema_sha256": _sha256_file(
                repo_root
                / "evaluation/schemas/real-cohort-freeze-evidence.v1.schema.json"
            ),
            "plan_schema_sha256": _sha256_file(
                repo_root
                / "evaluation/schemas/sequential-development-plan.v1.schema.json"
            ),
        },
        "candidate_summary": _candidate_summary(plan),
        "qualification_boundary": {
            "status": "pending_not_runnable",
            "immutable_image_digests": "pending_qualification",
            "ast_edit_fingerprints": "pending_qualification",
            "qualification_receipts": "pending_two_base_fail_and_two_gold_pass_runs",
            "executed_parser_source_sha256": "pending_qualification",
            "sealed_verifier_package_sha256": "pending_qualification",
        },
        "final_holdout": {
            "status": "sealed_not_read_or_run",
            "boundary": "three blocked internal repositories from committed v1 training manifest",
        },
    }


def validate_freeze_evidence(
    evidence: Mapping[str, Any],
    registry: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> None:
    """Check counts, disjointness and hash bindings in a freeze receipt."""

    validate_registry(registry)
    validate_sequential_plan(plan)
    if evidence.get("schema_version") != FREEZE_SCHEMA:
        raise RealCohortFreezeError("unexpected freeze-evidence schema")
    source = evidence.get("source")
    if not isinstance(source, dict) or source.get("revision") != DATASET_REVISION:
        raise RealCohortFreezeError("evidence does not bind the pinned source revision")
    if source.get("sha256") != SOURCE_SHA256 or source.get("rows") != SOURCE_ROWS:
        raise RealCohortFreezeError("evidence does not bind the pinned source bytes")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RealCohortFreezeError("evidence artifacts must be an object")
    registry_ref = artifacts.get("base_exclusion_registry")
    plan_ref = artifacts.get("sequential_plan")
    if not isinstance(registry_ref, dict) or not isinstance(plan_ref, dict):
        raise RealCohortFreezeError("evidence artifact references are incomplete")
    if registry_ref.get("canonical_sha256") != _canonical_sha256(registry):
        raise RealCohortFreezeError("registry canonical digest mismatch")
    if registry_ref.get("file_sha256") != _json_file_sha256(registry):
        raise RealCohortFreezeError("registry file digest mismatch")
    if plan_ref.get("canonical_sha256") != canonical_plan_sha256(plan):
        raise RealCohortFreezeError("plan canonical digest mismatch")
    if plan_ref.get("file_sha256") != _json_file_sha256(plan):
        raise RealCohortFreezeError("plan file digest mismatch")
    summary = _candidate_summary(plan)
    if evidence.get("candidate_summary") != summary:
        raise RealCohortFreezeError("candidate summary does not match plan")
    if summary["total_candidates"] != 456 or summary["unique_instance_ids"] != 456:
        raise RealCohortFreezeError("freeze must contain 456 disjoint candidates")
    if any(count != 456 for count in summary["unique_fingerprint_sets"].values()):
        raise RealCohortFreezeError(
            "candidate fingerprints must be cross-cohort disjoint"
        )


def freeze_from_parquet(
    source_path: Path,
    output_dir: Path,
    *,
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create and persist the deterministic pre-outcome candidate freeze."""

    registry = build_base_exclusion_registry(repo_root)
    try:
        plan = freeze_sequential_plan(
            iter_pinned_parquet(source_path),
            registry,
            plan_id=PLAN_ID,
            master_seed=MASTER_SEED,
        )
    except CandidateSelectionError as exc:
        raise RealCohortFreezeError(str(exc)) from exc
    evidence = build_freeze_evidence(
        repo_root=repo_root,
        source_path=source_path,
        registry=registry,
        plan=plan,
    )
    validate_freeze_evidence(evidence, registry, plan)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pre-plan-exclusions.json").write_bytes(_render_json(registry))
    (output_dir / "sequential-plan.json").write_bytes(_render_json(plan))
    (output_dir / "freeze-evidence.json").write_bytes(_render_json(evidence))
    return registry, plan, evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    freeze_from_parquet(
        args.parquet.resolve(),
        args.output_dir.resolve(),
        repo_root=args.repo_root.resolve(),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
