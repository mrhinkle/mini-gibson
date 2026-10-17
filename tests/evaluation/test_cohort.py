from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from evaluation.cohort import (
    CohortValidationError,
    agent_projection,
    canonical_projection_sha256,
    load_and_validate_lock,
    validate_lock,
)


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def registry(*entries: dict[str, str]) -> dict:
    return {
        "schema_version": "mini-gibson-exclusion-registry/v1",
        "registry_id": "test-registry",
        "source_digests": [{"name": "test-source", "sha256": sha("source")}],
        "entries": [dict(entry, source="test-source") for entry in entries],
    }


def task(index: int, *, mode: str = "pilot") -> dict:
    repo_number = index % (12 if mode == "pilot" else 24)
    language_number = index % (6 if mode == "pilot" else 8)
    repo = f"owner{repo_number}/repo{repo_number}"
    digest = f"sha256:{index + 1000:064x}"
    value = {
        "selection_rank": index + 1,
        "instance_id": f"sample__task-{index + 1}",
        "repo": repo,
        "source_identity": {
            "pr_url": f"https://github.com/{repo}/pull/{index + 1}",
            "pr_number": index + 1,
            "issue_urls": [f"https://github.com/{repo}/issues/{index + 1001}"],
            "merge_commit": f"{index + 1000:040x}",
            "episode_ids": [],
        },
        "base_commit": f"{index + 1:040x}",
        "problem_statement": f"Fix deterministic behavior for sample task {index + 1}.",
        "language": f"lang{language_number}",
        "license": "MIT",
        "split": mode,
        "image": {
            "reference": f"docker.io/example/task-{index + 1}@{digest}",
            "digest": digest,
            "platform": "linux/amd64",
            "workdir": "/repo",
        },
        "install_config_sha256": sha(f"install-{index}"),
        "task_projection_sha256": "",
        "fingerprints": {
            "issue_text_sha256": sha(f"issue-{index}"),
            "patch_sha256": sha(f"patch-{index}"),
            "test_patch_sha256": sha(f"test-patch-{index}"),
            "changed_files_sha256": sha(f"changed-files-{index}"),
            "ast_edits_sha256": sha(f"ast-{index}"),
            "image_cluster_sha256": sha(f"image-cluster-{index}"),
        },
        "qualification": {
            "status": "qualified",
            "receipt_sha256": sha(f"receipt-{index}"),
            "base_fail_repeats": 2,
            "gold_pass_repeats": 2,
        },
        "log_parser": "parse_log_pytest",
        "verify_timeout_s": 900,
    }
    value["task_projection_sha256"] = canonical_projection_sha256(value)
    return value


def lock(*, mode: str = "pilot") -> dict:
    count = 24 if mode == "pilot" else 144
    limits = (6, 12, 4) if mode == "pilot" else (8, 24, 8)
    return {
        "schema_version": "mini-gibson-real-repo-cohort/v1",
        "cohort_id": f"test-{mode}",
        "mode": mode,
        "source": {
            "dataset": "nebius/SWE-rebench-V2",
            "revision": "10483de0f50fe5da545942705a76c6150171af7f",
            "split": "train",
            "dataset_card_url": (
                "https://huggingface.co/datasets/nebius/SWE-rebench-V2/tree/"
                "10483de0f50fe5da545942705a76c6150171af7f"
            ),
        },
        "selection": {
            "policy_version": "swe-rebench-v2-balanced/v1",
            "seed": 414,
            "expected_tasks": count,
            "min_languages": limits[0],
            "min_repositories": limits[1],
            "max_tasks_per_repo": limits[2],
        },
        "exclusion_registry": {"path": "registry.json", "sha256": sha("registry")},
        "sealed_verifier_package": {"path": "sealed.tar", "sha256": sha("sealed")},
        "parser": {
            "source_repo": "https://github.com/SWE-rebench/SWE-rebench-V2",
            "source_revision": "c71902a8cf8d2b725f63d51f199f4d3e56f68d2d",
            "vendored_parser_sha256": sha("parser"),
        },
        "tasks": [task(index, mode=mode) for index in range(count)],
    }


def expect_invalid(value: dict, match: str, *, exclusions: dict | None = None) -> None:
    with pytest.raises(CohortValidationError, match=match):
        validate_lock(value, registry() if exclusions is None else exclusions)


def test_valid_pilot_and_development_locks() -> None:
    assert validate_lock(lock(), registry())["tasks"] == 24
    assert validate_lock(lock(mode="development"), registry())["tasks"] == 144


def test_wrong_cardinality_unknown_fields_and_duplicate_identity_fail() -> None:
    value = lock()
    value["tasks"].pop()
    expect_invalid(value, "exactly 24")

    value = lock()
    value["surprise"] = True
    expect_invalid(value, "unknown fields")

    value = lock()
    value["tasks"][1]["instance_id"] = value["tasks"][0]["instance_id"]
    expect_invalid(value, "duplicate task ID")


def test_mutable_image_unknown_parser_split_and_qualification_fail() -> None:
    value = lock()
    value["tasks"][0]["image"]["reference"] = "docker.io/example/task:latest"
    expect_invalid(value, "must end with")

    value = lock()
    value["tasks"][0]["log_parser"] = "eval"
    expect_invalid(value, "vendored allowlist")

    value = lock()
    value["tasks"][0]["split"] = "holdout"
    expect_invalid(value, "must equal lock mode")

    value = lock()
    value["tasks"][0]["qualification"]["gold_pass_repeats"] = 1
    expect_invalid(value, "exactly two")


def test_diversity_and_repository_cap_fail_closed() -> None:
    value = lock()
    for item in value["tasks"]:
        item["language"] = "python"
        item["task_projection_sha256"] = canonical_projection_sha256(item)
    expect_invalid(value, "language diversity")

    value = lock()
    for index in range(5):
        item = value["tasks"][index]
        item["repo"] = "owner0/repo0"
        item["source_identity"]["pr_url"] = f"https://github.com/owner0/repo0/pull/{index + 1}"
        item["source_identity"]["issue_urls"] = [
            f"https://github.com/owner0/repo0/issues/{index + 1001}"
        ]
        item["task_projection_sha256"] = canonical_projection_sha256(item)
    expect_invalid(value, "repository cap exceeded")


@pytest.mark.parametrize(
    ("kind", "value_getter"),
    [
        ("instance_id", lambda item: item["instance_id"]),
        ("repo", lambda item: item["repo"]),
        ("repo_pr", lambda item: f"{item['repo']}#{item['source_identity']['pr_number']}"),
        ("repo_issue", lambda item: f"{item['repo']}#1001"),
        ("base_commit", lambda item: item["base_commit"]),
        ("merge_commit", lambda item: item["source_identity"]["merge_commit"]),
        ("patch_sha256", lambda item: item["fingerprints"]["patch_sha256"]),
        ("image_cluster_sha256", lambda item: item["fingerprints"]["image_cluster_sha256"]),
    ],
)
def test_exclusion_registry_identity_overlap_fails(kind, value_getter) -> None:
    value = lock()
    blocked = registry({"kind": kind, "value": value_getter(value["tasks"][0])})
    expect_invalid(value, "overlaps exclusion registry", exclusions=blocked)


def test_statement_leakage_and_hidden_fields_fail() -> None:
    value = lock()
    value["tasks"][0]["problem_statement"] += " Hidden phrase MERGE-ANSWER."
    value["tasks"][0]["task_projection_sha256"] = canonical_projection_sha256(value["tasks"][0])
    blocked = registry({"kind": "statement_token", "value": "merge-answer"})
    expect_invalid(value, "hidden leakage token", exclusions=blocked)

    value = lock()
    value["tasks"][0]["gold_patch"] = "secret"
    expect_invalid(value, "hidden verifier field")


def test_agent_projection_is_an_allowlist_and_hash_bound() -> None:
    value = lock()
    projected = agent_projection(value, registry())
    assert set(projected[0]) == {
        "instance_id",
        "repo",
        "base_commit",
        "problem_statement",
        "language",
        "verify_timeout_s",
    }
    rendered = json.dumps(projected)
    for forbidden in ("source_identity", "fingerprints", "qualification", "log_parser", "image"):
        assert forbidden not in rendered

    value["tasks"][0]["task_projection_sha256"] = sha("wrong")
    with pytest.raises(CohortValidationError, match="allowlisted agent projection"):
        agent_projection(value, registry())


def test_loader_binds_registry_and_sealed_package_bytes(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    sealed_path = tmp_path / "sealed.tar"
    lock_path = tmp_path / "lock.json"
    registry_bytes = (json.dumps(registry(), sort_keys=True) + "\n").encode()
    registry_path.write_bytes(registry_bytes)
    sealed_path.write_bytes(b"sealed verifier package")
    value = lock()
    value["exclusion_registry"]["sha256"] = hashlib.sha256(registry_bytes).hexdigest()
    value["sealed_verifier_package"]["sha256"] = hashlib.sha256(sealed_path.read_bytes()).hexdigest()
    lock_path.write_text(json.dumps(value, sort_keys=True) + "\n")

    loaded = load_and_validate_lock(lock_path, registry_path, sealed_path)
    assert loaded.summary["tasks"] == 24
    assert len(loaded.tasks) == 24

    registry_path.write_text(registry_path.read_text() + " ")
    with pytest.raises(CohortValidationError, match="registry bytes"):
        load_and_validate_lock(lock_path, registry_path, sealed_path)

