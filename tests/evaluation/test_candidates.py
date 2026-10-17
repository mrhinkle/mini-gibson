from __future__ import annotations

import hashlib
import json

import pytest

from evaluation.candidates import (
    CandidateSelectionError,
    _source_pr,
    prepare_candidate_pool,
    select_candidates,
    select_prepared_candidates,
)

LANGUAGES = ("python", "ts", "go", "rust", "java", "ruby")


def registry(*entries: dict[str, str]) -> dict:
    return {
        "schema_version": "mini-gibson-exclusion-registry/v1",
        "registry_id": "test-registry",
        "source_digests": [
            {"name": "test-source", "sha256": hashlib.sha256(b"source").hexdigest()}
        ],
        "entries": [dict(entry, source="test-source") for entry in entries],
    }


def record(index: int) -> dict:
    repo_index = index % 12
    language = LANGUAGES[index % len(LANGUAGES)]
    repo = f"upstream{repo_index}/project{repo_index}"
    return {
        "instance_id": f"upstream__project-{index + 1}",
        "repo": repo,
        "base_commit": f"{index + 1:040x}",
        "problem_statement": f"Correct the formatter behavior for case {index + 1}.",
        "image_name": f"docker.io/swerebenchv2/project{repo_index}:{index + 1}",
        "language": language,
        "license": "MIT",
        "patch": (
            f"diff --git a/src/file{index}.py b/src/file{index}.py\n"
            f"--- a/src/file{index}.py\n+++ b/src/file{index}.py\n"
            "@@ -1 +1 @@\n-old value\n+new value\n"
        ),
        "test_patch": (
            f"diff --git a/tests/test_{index}.py b/tests/test_{index}.py\n"
            f"--- a/tests/test_{index}.py\n+++ b/tests/test_{index}.py\n"
            "@@ -1 +1 @@\n-old test\n+new test\n"
        ),
        "FAIL_TO_PASS": [f"tests/test_{index}.py::test_case"],
        "PASS_TO_PASS": [],
        "install_config": {
            "base_image_name": "python:3.12",
            "docker_specs": {"python_version": "3.12"},
            "install": [],
            "test_cmd": "pytest -q",
            "log_parser": "parse_log_pytest",
        },
        "meta": {
            "num_modified_files": 1,
            "num_modified_lines": 2,
            "pr_url": f"https://github.com/{repo}/pull/{index + 1}",
            "llm_metadata": {
                "code": "A",
                "confidence": 0.98,
                "detected_issues": {},
                "difficulty": ("easy", "medium", "hard")[index % 3],
                "external_urls": [f"https://github.com/{repo}/issues/{index + 1000}"],
                "intent_completeness": "complete",
                "pr_categories": ["bug_fix"],
                "reasoning": "",
                "test_alignment_issues": [],
            },
        },
    }


def test_candidate_selection_is_deterministic_non_runnable_and_non_leaking() -> None:
    rows = [record(index) for index in range(36)]
    first = select_candidates(rows, registry(), mode="pilot", seed=414)
    second = select_candidates(reversed(rows), registry(), mode="pilot", seed=414)
    assert first == second
    assert first["runnable"] is False
    assert first["counts"]["selected"] == 24
    assert len({item["language"] for item in first["candidates"]}) >= 6
    assert len({item["repo"] for item in first["candidates"]}) >= 12
    encoded = json.dumps(first).casefold()
    for forbidden in (
        "fail_to_pass",
        "pass_to_pass",
        'test_patch"',
        '"patch"',
        "problem_statement",
    ):
        assert forbidden not in encoded


def test_prepared_pool_matches_direct_selection_without_retaining_patches() -> None:
    rows = [record(index) for index in range(36)]
    direct = select_candidates(rows, registry(), mode="pilot", seed=414)
    pool = prepare_candidate_pool(iter(rows))
    prepared = select_prepared_candidates(pool, registry(), mode="pilot", seed=414)
    assert prepared == direct
    assert pool.records_seen == 36
    encoded = json.dumps(pool.eligible).casefold()
    for forbidden in ('"patch"', '"test_patch"', "problem_statement"):
        assert forbidden not in encoded


def test_registry_overlap_and_unsafe_records_are_counted() -> None:
    rows = [record(index) for index in range(36)]
    blocked = registry({"kind": "instance_id", "value": rows[0]["instance_id"]})
    rows[1]["install_config"]["test_cmd"] = "curl https://example.test"
    rows[2]["problem_statement"] = "Run a production database migration."
    report = select_candidates(rows, blocked, mode="pilot", seed=414)
    reasons = report["counts"]["rejected_by_reason"]
    assert reasons["registry_overlap_instance_id"] == 1
    assert reasons["network_or_service_test_command"] == 1
    assert reasons["high_risk_task_surface"] == 1


def test_frozen_cardinality_cannot_be_overridden() -> None:
    with pytest.raises(CandidateSelectionError, match="frozen pilot size"):
        select_candidates(
            [record(index) for index in range(36)],
            registry(),
            mode="pilot",
            seed=1,
            target=23,
        )


def test_source_pr_prefers_official_url_then_uses_instance_suffix() -> None:
    row = record(0)
    assert _source_pr(row, row["meta"]) == (row["meta"]["pr_url"], 1)
    row["meta"]["pr_url"] = None
    assert _source_pr(row, row["meta"]) == (
        "https://github.com/upstream0/project0/pull/1",
        1,
    )


def test_candidate_issues_keep_only_numeric_same_repo_urls() -> None:
    rows = [record(index) for index in range(36)]
    urls = rows[0]["meta"]["llm_metadata"]["external_urls"]
    urls.extend(
        [
            "https://github.com/upstream0/project0/issues/1000#issuecomment-7",
            "https://github.com/upstream0/project0/issues/new",
            "https://github.com/other/project/issues/22",
            "https://github.com/upstream0/project0/issues/23/comments",
        ]
    )
    pool = prepare_candidate_pool(rows)
    prepared = {row["instance_id"]: row for row in pool.eligible}
    assert prepared[rows[0]["instance_id"]]["source_issue_urls"] == [
        "https://github.com/upstream0/project0/issues/1000"
    ]


def test_insufficient_diversity_fails() -> None:
    rows = [record(index) for index in range(30)]
    for row in rows:
        row["language"] = "python"
    with pytest.raises(CandidateSelectionError, match="language diversity"):
        select_candidates(rows, registry(), mode="pilot", seed=414)


def test_selection_fails_closed_when_unique_fingerprints_cannot_fill_target() -> None:
    rows = [record(index) for index in range(36)]
    for index, row in enumerate(rows):
        row["patch"] = (
            "diff --git a/src/shared.py b/src/shared.py\n"
            "--- a/src/shared.py\n+++ b/src/shared.py\n"
            f"@@ -1 +1 @@\n-old {index}\n+new {index}\n"
        )
    with pytest.raises(
        CandidateSelectionError, match="could not reserve|cannot fill target"
    ):
        select_candidates(rows, registry(), mode="pilot", seed=414)
