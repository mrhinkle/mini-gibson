from __future__ import annotations

import copy
import hashlib

import pytest

from evaluation.cohort import canonical_projection_sha256, validate_registry
from evaluation.sequential import (
    OUTCOMES_SCHEMA,
    SequentialPlanError,
    assess_look,
    build_training_exclusion_registry,
    canonical_plan_sha256,
    exact_one_sided_mcnemar,
    finalize_execution_freeze,
    freeze_sequential_plan,
    paired_risk_difference_upper_bound,
    validate_sequential_plan,
)

LANGUAGES = (
    "python",
    "typescript",
    "go",
    "rust",
    "java",
    "ruby",
    "php",
    "swift",
    "scala",
    "csharp",
)


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def base_registry() -> dict:
    return {
        "schema_version": "mini-gibson-exclusion-registry/v1",
        "registry_id": "pre-plan-exclusions",
        "source_digests": [
            {"name": "sealed-holdout-fingerprints", "sha256": sha("holdouts")}
        ],
        "entries": [],
    }


def record(index: int) -> dict:
    repo_index = index % 60
    repo = f"upstream{repo_index}/project{repo_index}"
    language = LANGUAGES[index % len(LANGUAGES)]
    return {
        "instance_id": f"upstream__project-{index + 1}",
        "repo": repo,
        "base_commit": f"{index + 1:040x}",
        "problem_statement": f"Correct deterministic formatter behavior for case {index + 1}.",
        "image_name": f"docker.io/swerebenchv2/project{repo_index}:task-{index + 1}",
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
                "confidence": 0.99,
                "detected_issues": {},
                "difficulty": ("easy", "medium", "hard")[index % 3],
                "external_urls": [f"https://github.com/{repo}/issues/{index + 1001}"],
                "intent_completeness": "complete",
                "pr_categories": ["bug_fix"],
                "reasoning": "",
                "test_alignment_issues": [],
            },
        },
    }


@pytest.fixture(scope="module")
def plan() -> dict:
    return freeze_sequential_plan(
        [record(index) for index in range(620)],
        base_registry(),
        plan_id="sequential-dev-2026-10-17",
    )


def test_freeze_is_deterministic_disjoint_and_bounded(plan: dict) -> None:
    reversed_plan = freeze_sequential_plan(
        reversed([record(index) for index in range(620)]),
        base_registry(),
        plan_id="sequential-dev-2026-10-17",
    )
    assert plan == reversed_plan
    assert validate_sequential_plan(plan) == {
        "plan_id": "sequential-dev-2026-10-17",
        "candidates": 456,
        "development_max": 432,
        "looks": 3,
    }
    assert [cohort["target"] for cohort in plan["cohorts"]] == [24, 144, 144, 144]
    assert [cohort["alpha"] for cohort in plan["cohorts"]] == [0.0, 0.01, 0.015, 0.025]
    ids = [
        candidate["instance_id"]
        for cohort in plan["cohorts"]
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    assert len(ids) == len(set(ids)) == 456
    assert sum(cohort["alpha"] for cohort in plan["cohorts"]) == pytest.approx(0.05)


def test_plan_mutation_outcomes_and_optional_fourth_look_fail_closed(
    plan: dict, frozen_execution: dict
) -> None:
    changed = copy.deepcopy(plan)
    changed["inference"]["primary"]["looks"][0]["alpha"] = 0.05
    with pytest.raises(SequentialPlanError, match="preregistered exact paired design"):
        validate_sequential_plan(changed)

    changed = copy.deepcopy(plan)
    changed["cohorts"][0]["candidate_report"]["candidates"][0]["resolved"] = True
    with pytest.raises(SequentialPlanError, match="scored outcome is forbidden"):
        validate_sequential_plan(changed)

    changed = copy.deepcopy(plan)
    changed["cohorts"][0]["candidate_report"]["candidates"][0]["patch"] = "hidden"
    with pytest.raises(SequentialPlanError, match="unknown fields"):
        validate_sequential_plan(changed)

    outcomes = {
        "schema_version": OUTCOMES_SCHEMA,
        "plan_sha256": canonical_plan_sha256(plan),
        "execution_freeze_sha256": sha256_json(frozen_execution),
        "look_index": 4,
        "records": [],
    }
    with pytest.raises(SequentialPlanError, match="fourth look is forbidden"):
        assess_look(plan, frozen_execution, outcomes)


def qualified_lock(cohort: dict) -> dict:
    tasks = []
    for index, candidate in enumerate(cohort["candidate_report"]["candidates"]):
        digest = f"sha256:{index + cohort['seed'] * 1000 + 1:064x}"
        task = {
            "selection_rank": index + 1,
            "instance_id": candidate["instance_id"],
            "repo": candidate["repo"],
            "source_identity": {
                "pr_url": candidate["source_pr_url"],
                "pr_number": candidate["source_pr_number"],
                "issue_urls": candidate["source_issue_urls"],
                "merge_commit": sha(f"merge-{cohort['cohort_id']}-{index}")[:40],
                "episode_ids": [],
            },
            "base_commit": candidate["base_commit"],
            "problem_statement": f"Correct behavior for {candidate['instance_id']}.",
            "language": candidate["language"],
            "license": candidate["license"],
            "split": cohort["mode"],
            "image": {
                "reference": f"docker.io/example/{cohort['cohort_id']}-{index}@{digest}",
                "digest": digest,
                "platform": "linux/amd64",
                "workdir": "/repo",
            },
            "install_config_sha256": candidate["install_config_sha256"],
            "task_projection_sha256": "",
            "fingerprints": {
                **candidate["fingerprints"],
                "ast_edits_sha256": sha(f"ast-{cohort['cohort_id']}-{index}"),
            },
            "qualification": {
                "status": "qualified",
                "receipt_sha256": sha(f"receipt-{cohort['cohort_id']}-{index}"),
                "base_fail_repeats": 2,
                "gold_pass_repeats": 2,
            },
            "log_parser": candidate["log_parser"],
            "verify_timeout_s": 900,
        }
        task["task_projection_sha256"] = canonical_projection_sha256(task)
        tasks.append(task)
    limits = (6, 12, 4) if cohort["mode"] == "pilot" else (8, 24, 8)
    return {
        "schema_version": "mini-gibson-real-repo-cohort/v1",
        "cohort_id": cohort["cohort_id"],
        "mode": cohort["mode"],
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
            "seed": cohort["seed"],
            "expected_tasks": cohort["target"],
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
        "tasks": tasks,
    }


@pytest.fixture(scope="module")
def frozen_execution(plan: dict) -> dict:
    locks = {cohort["cohort_id"]: qualified_lock(cohort) for cohort in plan["cohorts"]}
    execution_freeze, _ = finalize_execution_freeze(plan, base_registry(), locks)
    return execution_freeze


def test_training_registry_requires_every_qualified_lock_and_all_fingerprints(
    plan: dict,
) -> None:
    locks = {cohort["cohort_id"]: qualified_lock(cohort) for cohort in plan["cohorts"]}
    result = build_training_exclusion_registry(plan, base_registry(), locks)
    validate_registry(result)
    entries = {(entry["kind"], entry["value"]) for entry in result["entries"]}
    assert sum(kind == "instance_id" for kind, _ in entries) == 456
    assert sum(kind == "ast_edits_sha256" for kind, _ in entries) == 456
    for cohort in plan["cohorts"]:
        for task in locks[cohort["cohort_id"]]["tasks"]:
            assert ("repo", task["repo"].casefold()) in entries
            for kind, value in task["fingerprints"].items():
                assert (kind, value) in entries

    missing = dict(locks)
    missing.pop("development-c")
    with pytest.raises(SequentialPlanError, match="must contain exactly"):
        build_training_exclusion_registry(plan, base_registry(), missing)

    changed = copy.deepcopy(locks)
    changed["development-a"]["tasks"][0]["fingerprints"]["patch_sha256"] = sha(
        "changed"
    )
    with pytest.raises(SequentialPlanError, match="frozen candidate fingerprint"):
        build_training_exclusion_registry(plan, base_registry(), changed)


def outcomes_for(
    plan: dict,
    execution_freeze: dict,
    look_index: int,
    *,
    v2_wins: int = 0,
    base_wins: int = 0,
) -> dict:
    candidates = [
        (cohort["cohort_id"], candidate["instance_id"])
        for cohort in plan["cohorts"]
        if 1 <= cohort["look_index"] <= look_index
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    records = []
    for index, (cohort_id, instance_id) in enumerate(candidates):
        base_resolved = v2_wins <= index < v2_wins + base_wins
        v2_resolved = index < v2_wins
        records.append(
            {
                "cohort_id": cohort_id,
                "instance_id": instance_id,
                "arms": {
                    "base": {
                        "resolved": base_resolved,
                        "malformed_response": False,
                        "policy_violation": False,
                        "tamper_detected": False,
                        "isolation_violation": False,
                        "receipt_inconsistent": False,
                    },
                    "v1": {
                        "resolved": False,
                        "malformed_response": False,
                        "policy_violation": False,
                        "tamper_detected": False,
                        "isolation_violation": False,
                        "receipt_inconsistent": False,
                    },
                    "v2": {
                        "resolved": v2_resolved,
                        "malformed_response": False,
                        "policy_violation": False,
                        "tamper_detected": False,
                        "isolation_violation": False,
                        "receipt_inconsistent": False,
                    },
                },
            }
        )
    return {
        "schema_version": OUTCOMES_SCHEMA,
        "plan_sha256": canonical_plan_sha256(plan),
        "execution_freeze_sha256": sha256_json(execution_freeze),
        "look_index": look_index,
        "records": records,
    }


def sha256_json(value: dict) -> str:
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_exact_primary_efficacy_and_safety_gates(
    plan: dict, frozen_execution: dict
) -> None:
    assert exact_one_sided_mcnemar(20, 0) == pytest.approx(1 / 2**20)
    outcomes = outcomes_for(plan, frozen_execution, 1, v2_wins=20)
    assessment = assess_look(plan, frozen_execution, outcomes)
    assert assessment["primary"]["absolute_uplift"] == pytest.approx(20 / 144)
    assert assessment["primary"]["alpha_crossed"] is True
    assert assessment["safety"]["malformed_noninferiority_met"] is True
    assert assessment["safety"]["malformed_risk_difference_upper_95"] == pytest.approx(
        paired_risk_difference_upper_bound(0, 0, 144)
    )
    assert assessment["primary"]["sequential_adjusted_p"] == pytest.approx(
        assessment["primary"]["p_value_one_sided_exact_mcnemar"] / 0.20
    )
    assert assessment["decision"] == "stop_promote_to_final_holdout_decision"
    assert assessment["final_holdout_opened"] is False

    outcomes["records"][0]["arms"]["v1"]["policy_violation"] = True
    assessment = assess_look(plan, frozen_execution, outcomes)
    assert assessment["decision"] == "stop_safety_failure"
    assert assessment["safety"]["integrity_events"]

    outcomes = outcomes_for(plan, frozen_execution, 1, v2_wins=20)
    outcomes["records"][0]["arms"]["base"]["receipt_inconsistent"] = True
    assessment = assess_look(plan, frozen_execution, outcomes)
    assert assessment["decision"] == "stop_safety_failure"
    assert (
        assessment["safety"]["integrity_events"][0]["field"] == "receipt_inconsistent"
    )


def test_malformed_noninferiority_futility_and_maximum_n(
    plan: dict, frozen_execution: dict
) -> None:
    unsafe = outcomes_for(plan, frozen_execution, 1, v2_wins=20)
    for row in unsafe["records"][:30]:
        row["arms"]["v2"]["malformed_response"] = True
    assessment = assess_look(plan, frozen_execution, unsafe)
    assert assessment["safety"]["malformed_noninferiority_met"] is False
    assert assessment["safety"]["interim_harm_stop"] is True
    assert assessment["decision"] == "stop_safety_failure"

    futile = outcomes_for(plan, frozen_execution, 1, base_wins=80)
    assessment = assess_look(plan, frozen_execution, futile)
    assert assessment["futility"]["conditional_power_below_0_10"] is True
    assert assessment["decision"] == "stop_nonbinding_futility"

    impossible = outcomes_for(plan, frozen_execution, 2, base_wins=130)
    assessment = assess_look(plan, frozen_execution, impossible)
    assert (
        assessment["futility"]["mathematically_impossible_to_reach_22_net_wins"] is True
    )
    assert assessment["futility"]["stop"] is True

    maximum = outcomes_for(plan, frozen_execution, 3)
    assessment = assess_look(plan, frozen_execution, maximum)
    assert assessment["cumulative_n"] == 432
    assert assessment["familywise_alpha_allocated_through_look"] == pytest.approx(0.05)
    assert assessment["decision"] == "stop_no_promotion_at_maximum_n"


def test_exact_paired_risk_difference_bound_zero_low_boundary_and_small_n() -> None:
    # Zero discordance is safe once the formal cohort is large enough; the old
    # conditional-OR test incorrectly required base-only malformed responses.
    assert paired_risk_difference_upper_bound(0, 0, 144) < 0.05

    # Low discordance is handled without requiring either arm to be sloppy.
    assert paired_risk_difference_upper_bound(1, 0, 144) < 0.05
    assert paired_risk_difference_upper_bound(0, 1, 144) < 0.05

    # At N=144, U=2 is just within the frozen five-point margin while U=3 is not.
    assert paired_risk_difference_upper_bound(2, 0, 144) <= 0.05
    assert paired_risk_difference_upper_bound(3, 0, 144) > 0.05

    # A tiny sample cannot prove five-point non-inferiority even with no events.
    assert paired_risk_difference_upper_bound(0, 0, 50) > 0.05


def test_outcome_membership_and_plan_digest_are_fail_closed(
    plan: dict, frozen_execution: dict
) -> None:
    outcomes = outcomes_for(plan, frozen_execution, 1)
    outcomes["plan_sha256"] = sha("different plan")
    with pytest.raises(SequentialPlanError, match="exact frozen plan"):
        assess_look(plan, frozen_execution, outcomes)

    outcomes = outcomes_for(plan, frozen_execution, 1)
    outcomes["records"][0]["instance_id"] = "unplanned-task"
    with pytest.raises(SequentialPlanError, match="not in the frozen cumulative look"):
        assess_look(plan, frozen_execution, outcomes)

    outcomes = outcomes_for(plan, frozen_execution, 1)
    changed_freeze = copy.deepcopy(frozen_execution)
    changed_freeze["training_exclusion_registry_sha256"] = sha("substituted")
    with pytest.raises(SequentialPlanError, match="pre-outcome execution freeze"):
        assess_look(plan, changed_freeze, outcomes)
