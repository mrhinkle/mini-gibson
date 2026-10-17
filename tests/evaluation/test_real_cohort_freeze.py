from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evaluation.freeze_real_cohorts import (
    DATASET_REVISION,
    SOURCE_SHA256,
    RealCohortFreezeError,
    _render_json,
    build_base_exclusion_registry,
    iter_pinned_parquet,
    validate_freeze_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FREEZE_ROOT = REPO_ROOT / "evaluation/frozen/mini-gibson-v2-sequential-2026-10-17"


def load(name: str) -> dict:
    return json.loads((FREEZE_ROOT / name).read_text(encoding="utf-8"))


def test_committed_freeze_is_bound_disjoint_and_canonically_serialized() -> None:
    registry = load("pre-plan-exclusions.json")
    plan = load("sequential-plan.json")
    evidence = load("freeze-evidence.json")
    validate_freeze_evidence(evidence, registry, plan)

    assert plan["source"]["revision"] == DATASET_REVISION
    assert evidence["source"]["sha256"] == SOURCE_SHA256
    assert [cohort["target"] for cohort in plan["cohorts"]] == [24, 144, 144, 144]
    candidates = [
        candidate
        for cohort in plan["cohorts"]
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    assert len(candidates) == len({row["instance_id"] for row in candidates}) == 456
    for fingerprint in (
        "issue_text_sha256",
        "patch_sha256",
        "test_patch_sha256",
        "changed_files_sha256",
        "image_cluster_sha256",
    ):
        assert len({row["fingerprints"][fingerprint] for row in candidates}) == 456

    assert (FREEZE_ROOT / "pre-plan-exclusions.json").read_bytes() == _render_json(
        registry
    )
    assert (FREEZE_ROOT / "sequential-plan.json").read_bytes() == _render_json(plan)
    assert (FREEZE_ROOT / "freeze-evidence.json").read_bytes() == _render_json(evidence)


def test_base_registry_regenerates_without_reading_holdout_task_files() -> None:
    committed = load("pre-plan-exclusions.json")
    assert build_base_exclusion_registry(REPO_ROOT) == committed
    sources = {row["name"] for row in committed["source_digests"]}
    assert sources == {
        "v1-openhands-training-and-sealed-repo-boundary",
        "observational-task-manifest",
        "prior-development-fixture-identities",
    }
    repos = {row["value"] for row in committed["entries"] if row["kind"] == "repo"}
    assert {
        "the-aie/chatterbuilt",
        "the-aie/conference-os",
        "the-aie/the-gibson",
    } <= repos


def test_candidate_manifests_contain_no_outcomes_or_hidden_patch_bytes() -> None:
    plan = load("sequential-plan.json")
    encoded = json.dumps(
        [cohort["candidate_report"] for cohort in plan["cohorts"]]
    ).casefold()
    for forbidden in (
        '"resolved"',
        '"malformed_response"',
        '"policy_violation"',
        '"tamper_detected"',
        '"test_patch"',
        '"patch"',
        '"problem_statement"',
    ):
        assert forbidden not in encoded


def test_evidence_schema_pins_source_and_fixed_sizes() -> None:
    schema = json.loads(
        (
            REPO_ROOT / "evaluation/schemas/real-cohort-freeze-evidence.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    source = schema["properties"]["source"]["properties"]
    summary = schema["properties"]["candidate_summary"]["properties"]
    assert source["revision"]["const"] == DATASET_REVISION
    assert source["sha256"]["const"] == SOURCE_SHA256
    assert summary["total_candidates"]["const"] == 456
    assert summary["development_candidates"]["const"] == 432


def test_hash_substitution_and_wrong_source_bytes_fail_closed(tmp_path: Path) -> None:
    registry = load("pre-plan-exclusions.json")
    plan = load("sequential-plan.json")
    evidence = load("freeze-evidence.json")
    changed = copy.deepcopy(evidence)
    changed["source"]["sha256"] = "0" * 64
    with pytest.raises(RealCohortFreezeError, match="pinned source bytes"):
        validate_freeze_evidence(changed, registry, plan)

    wrong = tmp_path / "source.parquet"
    wrong.write_bytes(b"not the pinned parquet")
    with pytest.raises(RealCohortFreezeError, match="source SHA-256 mismatch"):
        next(iter(iter_pinned_parquet(wrong)))
