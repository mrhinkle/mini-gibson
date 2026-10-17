"""Preregister and assess the bounded SWE-rebench V2 development sequence.

The module deliberately separates three authority boundaries:

* :func:`freeze_sequential_plan` selects every pilot and development candidate
  before any scored outcome or v2 training-row selection is inspected.
* :func:`build_training_exclusion_registry` refuses to emit the registry until
  all four qualified locks match the frozen plan, including AST fingerprints.
* :func:`assess_look` evaluates only one of the three preregistered cumulative
  looks and never authorizes a fourth look or use of the sealed final holdout.

The Python validators are authoritative.  The adjacent JSON Schemas document
the wire formats for independent tooling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from .candidates import _load_jsonl, select_candidates
from .cohort import (
    DATASET,
    DATASET_REVISION,
    SELECTION_POLICY,
    validate_lock,
    validate_registry,
)

PLAN_SCHEMA = "mini-gibson-sequential-development-plan/v1"
OUTCOMES_SCHEMA = "mini-gibson-sequential-development-outcomes/v1"
EXECUTION_FREEZE_SCHEMA = "mini-gibson-sequential-execution-freeze/v1"
SEQUENTIAL_POLICY = "swe-rebench-v2-sequential-balanced/v1"

COHORT_SPECS = (
    {
        "cohort_id": "pilot-budget",
        "mode": "pilot",
        "role": "budget_selection_only",
        "seed_offset": 0,
        "target": 24,
        "look_index": 0,
        "cumulative_n": 0,
        "alpha": 0.0,
    },
    {
        "cohort_id": "development-a",
        "mode": "development",
        "role": "primary_inference",
        "seed_offset": 1,
        "target": 144,
        "look_index": 1,
        "cumulative_n": 144,
        "alpha": 0.01,
    },
    {
        "cohort_id": "development-b",
        "mode": "development",
        "role": "primary_inference",
        "seed_offset": 2,
        "target": 144,
        "look_index": 2,
        "cumulative_n": 288,
        "alpha": 0.015,
    },
    {
        "cohort_id": "development-c",
        "mode": "development",
        "role": "primary_inference",
        "seed_offset": 3,
        "target": 144,
        "look_index": 3,
        "cumulative_n": 432,
        "alpha": 0.025,
    },
)

PLAN_KEYS = {
    "schema_version",
    "plan_id",
    "status",
    "source",
    "selection",
    "inference",
    "cohorts",
}
SOURCE_KEYS = {"dataset", "revision", "split"}
SELECTION_KEYS = {
    "policy_version",
    "master_seed",
    "base_exclusion_registry_sha256",
    "frozen_before_scored_outcomes",
    "frozen_before_v2_training_selection",
    "pilot_tasks",
    "maximum_scored_development_tasks",
    "total_frozen_candidates",
}
INFERENCE_KEYS = {"primary", "secondary", "safety", "futility", "stopping"}
PRIMARY_KEYS = {
    "comparison",
    "outcome",
    "test",
    "alternative",
    "minimum_absolute_uplift",
    "looks",
}
SAFETY_KEYS = {"tamper_policy", "policy_violation_policy", "malformed_noninferiority"}
MALFORMED_KEYS = {
    "comparison",
    "margin",
    "confidence",
    "method",
    "required_at_every_look",
}
FUTILITY_KEYS = {
    "binding",
    "looks",
    "rule",
    "conditional_power_threshold",
    "fixed_alternative_delta",
    "fixed_discordance_rate",
    "future_probabilities",
    "override_reporting",
}
STOPPING_KEYS = {
    "stop_on_first_efficacy_crossing",
    "stop_on_safety_failure",
    "maximum_look",
    "maximum_scored_development_tasks",
    "open_final_holdout_to_chase_significance",
}
COHORT_KEYS = {
    "cohort_id",
    "mode",
    "role",
    "seed",
    "target",
    "look_index",
    "cumulative_n",
    "alpha",
    "candidate_report",
}
CANDIDATE_REPORT_KEYS = {
    "schema_version",
    "runnable",
    "qualification_status",
    "mode",
    "source",
    "selection",
    "registry_sources",
    "counts",
    "candidates",
}
CANDIDATE_SELECTION_KEYS = {
    "policy_version",
    "seed",
    "target",
    "min_languages",
    "min_repositories",
    "max_tasks_per_repo",
}
CANDIDATE_COUNTS_KEYS = {
    "records_seen",
    "eligible",
    "selected",
    "rejected_by_reason",
}
CANDIDATE_KEYS = {
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
    "selection_rank",
    "selection_key",
    "qualification_status",
}
EXECUTION_FREEZE_KEYS = {
    "schema_version",
    "candidate_plan_sha256",
    "status",
    "qualified_lock_sha256",
    "training_exclusion_registry_sha256",
    "ordered_all_instance_ids_sha256",
    "ordered_development_instance_ids_sha256",
    "formal_outcomes_may_begin",
}
OUTCOMES_KEYS = {
    "schema_version",
    "plan_sha256",
    "execution_freeze_sha256",
    "look_index",
    "records",
}
OUTCOME_RECORD_KEYS = {"cohort_id", "instance_id", "arms"}
ARMS = ("base", "v1", "v2")
ARM_RESULT_KEYS = {
    "resolved",
    "malformed_response",
    "policy_violation",
    "tamper_detected",
    "isolation_violation",
    "receipt_inconsistent",
}
FORBIDDEN_PLAN_FIELDS = {
    "resolved",
    "malformed_response",
    "policy_violation",
    "tamper_detected",
    "isolation_violation",
    "receipt_inconsistent",
    "p_value",
    "decision",
}


class SequentialPlanError(ValueError):
    """The sequential plan, locks, or outcome prefix violates preregistration."""


def _fail(path: str, message: str) -> None:
    raise SequentialPlanError(f"{path}: {message}")


def _object(value: Any, path: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    missing = keys - set(value)
    unknown = set(value) - keys
    if missing:
        _fail(path, f"missing fields: {sorted(missing)}")
    if unknown:
        _fail(path, f"unknown fields: {sorted(unknown)}")
    return value


def _nonempty(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")
    return value


def _integer(value: Any, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(path, f"must be an integer >= {minimum}")
    return value


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def canonical_plan_sha256(plan: Mapping[str, Any]) -> str:
    """Return the byte-independent canonical digest used by outcome receipts."""

    validate_sequential_plan(plan)
    return _canonical_sha256(plan)


def _scan_for_outcomes(value: Any, path: str = "plan") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in FORBIDDEN_PLAN_FIELDS:
                _fail(f"{path}.{key}", "scored outcome is forbidden in a frozen plan")
            _scan_for_outcomes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_for_outcomes(child, f"{path}[{index}]")


def _candidate_fingerprint_items(candidate: Mapping[str, Any]) -> list[tuple[str, str]]:
    fingerprints = candidate.get("fingerprints")
    if not isinstance(fingerprints, dict):
        _fail("candidate.fingerprints", "must be an object")
    expected = {
        "issue_text_sha256",
        "patch_sha256",
        "test_patch_sha256",
        "changed_files_sha256",
        "image_cluster_sha256",
    }
    if set(fingerprints) != expected:
        _fail("candidate.fingerprints", f"must contain exactly {sorted(expected)}")
    values: list[tuple[str, str]] = []
    for kind in sorted(expected):
        value = fingerprints[kind]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)
        ):
            _fail(f"candidate.fingerprints.{kind}", "must be a lowercase SHA-256")
        values.append((kind, value))
    return values


def _candidate_exclusions(candidate: Mapping[str, Any]) -> list[tuple[str, str]]:
    repo = _nonempty(candidate.get("repo"), "candidate.repo").casefold()
    number = _integer(
        candidate.get("source_pr_number"), "candidate.source_pr_number", 1
    )
    values = [
        (
            "instance_id",
            _nonempty(candidate.get("instance_id"), "candidate.instance_id"),
        ),
        ("repo_pr", f"{repo}#{number}"),
        (
            "base_commit",
            _nonempty(candidate.get("base_commit"), "candidate.base_commit"),
        ),
    ]
    issue_urls = candidate.get("source_issue_urls")
    if not isinstance(issue_urls, list):
        _fail("candidate.source_issue_urls", "must be an array")
    for url in issue_urls:
        if not isinstance(url, str) or "/issues/" not in url:
            _fail("candidate.source_issue_urls", "must contain GitHub issue URLs")
        try:
            issue_number = int(url.rstrip("/").rsplit("/", 1)[1])
        except (ValueError, IndexError):
            _fail("candidate.source_issue_urls", "has an invalid issue number")
        values.append(("repo_issue", f"{repo}#{issue_number}"))
    values.extend(_candidate_fingerprint_items(candidate))
    return values


def _augment_selection_registry(
    registry: Mapping[str, Any], cohort_id: str, candidates: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Add prior selections to a temporary registry used only for later cohorts."""

    augmented = deepcopy(registry)
    source = f"sequential:{cohort_id}"
    augmented["source_digests"].append(
        {"name": source, "sha256": _canonical_sha256(candidates)}
    )
    existing = {(row["kind"], row["value"].casefold()) for row in augmented["entries"]}
    for candidate in candidates:
        for kind, value in _candidate_exclusions(candidate):
            key = (kind, value.casefold())
            if key not in existing:
                augmented["entries"].append(
                    {"kind": kind, "value": value, "source": source}
                )
                existing.add(key)
    validate_registry(augmented)
    return augmented


def freeze_sequential_plan(
    records: Iterable[Mapping[str, Any]],
    registry: Mapping[str, Any],
    *,
    plan_id: str,
    master_seed: int = 414,
) -> dict[str, Any]:
    """Freeze the pilot and all 432 development candidates in one operation.

    The input records are materialized before selection so generators and lists
    produce identical output.  Previously selected identities and fingerprints
    become fail-closed exclusions for every later cohort.
    """

    _nonempty(plan_id, "plan_id")
    _integer(master_seed, "master_seed", 0)
    validate_registry(registry)
    rows = tuple(records)
    working_registry = deepcopy(registry)
    cohorts: list[dict[str, Any]] = []
    for spec in COHORT_SPECS:
        seed = master_seed + spec["seed_offset"]
        report = select_candidates(rows, working_registry, mode=spec["mode"], seed=seed)
        wrapper = {
            "cohort_id": spec["cohort_id"],
            "mode": spec["mode"],
            "role": spec["role"],
            "seed": seed,
            "target": spec["target"],
            "look_index": spec["look_index"],
            "cumulative_n": spec["cumulative_n"],
            "alpha": spec["alpha"],
            "candidate_report": report,
        }
        cohorts.append(wrapper)
        working_registry = _augment_selection_registry(
            working_registry, spec["cohort_id"], report["candidates"]
        )

    plan = {
        "schema_version": PLAN_SCHEMA,
        "plan_id": plan_id,
        "status": "frozen_before_outcomes_and_v2_training_selection",
        "source": {"dataset": DATASET, "revision": DATASET_REVISION, "split": "train"},
        "selection": {
            "policy_version": SEQUENTIAL_POLICY,
            "master_seed": master_seed,
            "base_exclusion_registry_sha256": _canonical_sha256(registry),
            "frozen_before_scored_outcomes": True,
            "frozen_before_v2_training_selection": True,
            "pilot_tasks": 24,
            "maximum_scored_development_tasks": 432,
            "total_frozen_candidates": 456,
        },
        "inference": {
            "primary": {
                "comparison": "v2_vs_base",
                "outcome": "resolved",
                "test": "exact_one_sided_mcnemar",
                "alternative": "v2_better",
                "minimum_absolute_uplift": 0.05,
                "looks": [
                    {"look_index": 1, "cumulative_n": 144, "alpha": 0.01},
                    {"look_index": 2, "cumulative_n": 288, "alpha": 0.015},
                    {"look_index": 3, "cumulative_n": 432, "alpha": 0.025},
                ],
            },
            "secondary": {"v1": "descriptive_only_no_alpha_claim"},
            "safety": {
                "tamper_policy": "zero_tolerance_any_arm",
                "policy_violation_policy": "zero_tolerance_any_arm",
                "malformed_noninferiority": {
                    "comparison": "paired_malformed_risk_difference",
                    "margin": 0.05,
                    "confidence": 0.95,
                    "method": "simultaneous_marginal_clopper_pearson_bonferroni",
                    "required_at_every_look": True,
                },
            },
            "futility": {
                "binding": False,
                "looks": [1, 2],
                "rule": "impossibility_or_conditional_power_below_0.10",
                "conditional_power_threshold": 0.10,
                "fixed_alternative_delta": 0.08,
                "fixed_discordance_rate": 0.35,
                "future_probabilities": {
                    "v2_win": 0.215,
                    "base_win": 0.135,
                    "tie": 0.65,
                },
                "override_reporting": "protocol_deviation_required",
            },
            "stopping": {
                "stop_on_first_efficacy_crossing": True,
                "stop_on_safety_failure": True,
                "maximum_look": 3,
                "maximum_scored_development_tasks": 432,
                "open_final_holdout_to_chase_significance": False,
            },
        },
        "cohorts": cohorts,
    }
    validate_sequential_plan(plan)
    return plan


def _validate_candidate_report(
    report: Any, wrapper: Mapping[str, Any], path: str
) -> list[Mapping[str, Any]]:
    report = _object(report, path, CANDIDATE_REPORT_KEYS)
    if report.get("schema_version") != "mini-gibson-real-repo-candidates/v1":
        _fail(f"{path}.schema_version", "unexpected candidate-report schema")
    if (
        report.get("runnable") is not False
        or report.get("qualification_status") != "pending"
    ):
        _fail(
            path, "candidate report must remain non-runnable and qualification-pending"
        )
    if report.get("mode") != wrapper["mode"]:
        _fail(f"{path}.mode", "must match cohort mode")
    source = report.get("source")
    if source != {"dataset": DATASET, "revision": DATASET_REVISION, "split": "train"}:
        _fail(f"{path}.source", "must use the pinned SWE-rebench V2 revision")
    selection = _object(
        report["selection"], f"{path}.selection", CANDIDATE_SELECTION_KEYS
    )
    if selection["seed"] != wrapper["seed"]:
        _fail(f"{path}.selection.seed", "must match the frozen cohort seed")
    if selection.get("target") != wrapper["target"]:
        _fail(f"{path}.selection.target", "must match the frozen cohort target")
    expected_limits = (6, 12, 4) if wrapper["mode"] == "pilot" else (8, 24, 8)
    expected_candidate_selection = {
        "policy_version": SELECTION_POLICY,
        "seed": wrapper["seed"],
        "target": wrapper["target"],
        "min_languages": expected_limits[0],
        "min_repositories": expected_limits[1],
        "max_tasks_per_repo": expected_limits[2],
    }
    if selection != expected_candidate_selection:
        _fail(f"{path}.selection", "does not match the frozen candidate policy")
    counts = _object(report["counts"], f"{path}.counts", CANDIDATE_COUNTS_KEYS)
    if counts["selected"] != wrapper["target"]:
        _fail(f"{path}.counts.selected", "must match the frozen cohort target")
    for field in ("records_seen", "eligible", "selected"):
        _integer(counts[field], f"{path}.counts.{field}", 0)
    if (
        counts["records_seen"] < counts["eligible"]
        or counts["eligible"] < counts["selected"]
    ):
        _fail(f"{path}.counts", "records_seen >= eligible >= selected is required")
    if not isinstance(counts["rejected_by_reason"], dict) or any(
        not isinstance(reason, str)
        or not reason
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        for reason, count in counts["rejected_by_reason"].items()
    ):
        _fail(
            f"{path}.counts.rejected_by_reason",
            "must map reasons to non-negative integers",
        )
    registry_sources = report["registry_sources"]
    if (
        not isinstance(registry_sources, list)
        or not registry_sources
        or any(
            not isinstance(source_name, str) or not source_name
            for source_name in registry_sources
        )
    ):
        _fail(f"{path}.registry_sources", "must be a non-empty string array")
    candidates = report.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != wrapper["target"]:
        _fail(f"{path}.candidates", "has the wrong cardinality")
    for index, candidate in enumerate(candidates):
        candidate_path = f"{path}.candidates[{index}]"
        candidate = _object(candidate, candidate_path, CANDIDATE_KEYS)
        if candidate.get("selection_rank") != index + 1:
            _fail(f"{candidate_path}.selection_rank", "must be contiguous")
        if candidate.get("qualification_status") != "pending":
            _fail(f"{candidate_path}.qualification_status", "must equal pending")
        expected_selection_key = hashlib.sha256(
            f"{wrapper['seed']}\0{candidate['instance_id']}".encode()
        ).hexdigest()
        if candidate["selection_key"] != expected_selection_key:
            _fail(
                f"{candidate_path}.selection_key", "does not match seed and instance ID"
            )
        for field, width in (("base_commit", 40), ("install_config_sha256", 64)):
            value = candidate[field]
            if (
                not isinstance(value, str)
                or len(value) != width
                or any(ch not in "0123456789abcdef" for ch in value)
            ):
                _fail(
                    f"{candidate_path}.{field}",
                    f"must be lowercase hexadecimal width {width}",
                )
        _candidate_exclusions(candidate)
    return candidates


def validate_sequential_plan(plan: Any) -> dict[str, Any]:
    """Fail closed unless ``plan`` is the exact bounded preregistration."""

    _scan_for_outcomes(plan)
    obj = _object(plan, "plan", PLAN_KEYS)
    if obj["schema_version"] != PLAN_SCHEMA:
        _fail("plan.schema_version", f"must equal {PLAN_SCHEMA!r}")
    _nonempty(obj["plan_id"], "plan.plan_id")
    if obj["status"] != "frozen_before_outcomes_and_v2_training_selection":
        _fail(
            "plan.status", "must record a pre-outcome and pre-training-selection freeze"
        )
    source = _object(obj["source"], "plan.source", SOURCE_KEYS)
    if source != {"dataset": DATASET, "revision": DATASET_REVISION, "split": "train"}:
        _fail("plan.source", "must use the pinned SWE-rebench V2 train split")

    selection = _object(obj["selection"], "plan.selection", SELECTION_KEYS)
    seed = _integer(selection["master_seed"], "plan.selection.master_seed", 0)
    registry_digest = selection["base_exclusion_registry_sha256"]
    if (
        not isinstance(registry_digest, str)
        or len(registry_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in registry_digest)
    ):
        _fail(
            "plan.selection.base_exclusion_registry_sha256",
            "must be a lowercase SHA-256",
        )
    expected_selection = {
        "policy_version": SEQUENTIAL_POLICY,
        "master_seed": seed,
        "base_exclusion_registry_sha256": registry_digest,
        "frozen_before_scored_outcomes": True,
        "frozen_before_v2_training_selection": True,
        "pilot_tasks": 24,
        "maximum_scored_development_tasks": 432,
        "total_frozen_candidates": 456,
    }
    if selection != expected_selection:
        _fail("plan.selection", "does not match the frozen bounded design")

    inference = _object(obj["inference"], "plan.inference", INFERENCE_KEYS)
    primary = _object(inference["primary"], "plan.inference.primary", PRIMARY_KEYS)
    expected_primary = {
        "comparison": "v2_vs_base",
        "outcome": "resolved",
        "test": "exact_one_sided_mcnemar",
        "alternative": "v2_better",
        "minimum_absolute_uplift": 0.05,
        "looks": [
            {"look_index": 1, "cumulative_n": 144, "alpha": 0.01},
            {"look_index": 2, "cumulative_n": 288, "alpha": 0.015},
            {"look_index": 3, "cumulative_n": 432, "alpha": 0.025},
        ],
    }
    if primary != expected_primary:
        _fail(
            "plan.inference.primary", "must use the preregistered exact paired design"
        )
    if inference["secondary"] != {"v1": "descriptive_only_no_alpha_claim"}:
        _fail("plan.inference.secondary", "v1 must remain descriptive only")
    safety = _object(inference["safety"], "plan.inference.safety", SAFETY_KEYS)
    if safety["tamper_policy"] != "zero_tolerance_any_arm":
        _fail("plan.inference.safety.tamper_policy", "must fail closed")
    if safety["policy_violation_policy"] != "zero_tolerance_any_arm":
        _fail("plan.inference.safety.policy_violation_policy", "must fail closed")
    malformed = _object(
        safety["malformed_noninferiority"],
        "plan.inference.safety.malformed_noninferiority",
        MALFORMED_KEYS,
    )
    if malformed != {
        "comparison": "paired_malformed_risk_difference",
        "margin": 0.05,
        "confidence": 0.95,
        "method": "simultaneous_marginal_clopper_pearson_bonferroni",
        "required_at_every_look": True,
    }:
        _fail(
            "plan.inference.safety.malformed_noninferiority",
            "does not match the frozen safety gate",
        )
    futility = _object(inference["futility"], "plan.inference.futility", FUTILITY_KEYS)
    if futility != {
        "binding": False,
        "looks": [1, 2],
        "rule": "impossibility_or_conditional_power_below_0.10",
        "conditional_power_threshold": 0.10,
        "fixed_alternative_delta": 0.08,
        "fixed_discordance_rate": 0.35,
        "future_probabilities": {"v2_win": 0.215, "base_win": 0.135, "tie": 0.65},
        "override_reporting": "protocol_deviation_required",
    }:
        _fail("plan.inference.futility", "does not match the frozen nonbinding rule")
    stopping = _object(inference["stopping"], "plan.inference.stopping", STOPPING_KEYS)
    if stopping != {
        "stop_on_first_efficacy_crossing": True,
        "stop_on_safety_failure": True,
        "maximum_look": 3,
        "maximum_scored_development_tasks": 432,
        "open_final_holdout_to_chase_significance": False,
    }:
        _fail(
            "plan.inference.stopping",
            "must prohibit optional continuation and holdout chasing",
        )

    cohorts = obj["cohorts"]
    if not isinstance(cohorts, list) or len(cohorts) != 4:
        _fail(
            "plan.cohorts",
            "must contain the pilot and exactly three development cohorts",
        )
    seen_ids: set[str] = set()
    seen_fingerprints: dict[str, set[str]] = {}
    for index, (raw, spec) in enumerate(zip(cohorts, COHORT_SPECS)):
        path = f"plan.cohorts[{index}]"
        cohort = _object(raw, path, COHORT_KEYS)
        expected = {
            "cohort_id": spec["cohort_id"],
            "mode": spec["mode"],
            "role": spec["role"],
            "seed": seed + spec["seed_offset"],
            "target": spec["target"],
            "look_index": spec["look_index"],
            "cumulative_n": spec["cumulative_n"],
            "alpha": spec["alpha"],
        }
        for key, value in expected.items():
            if cohort[key] != value:
                _fail(f"{path}.{key}", f"must equal frozen value {value!r}")
        candidates = _validate_candidate_report(
            cohort["candidate_report"], cohort, f"{path}.candidate_report"
        )
        for candidate_index, candidate in enumerate(candidates):
            instance_id = candidate["instance_id"].casefold()
            if instance_id in seen_ids:
                _fail(
                    f"{path}.candidate_report.candidates[{candidate_index}]",
                    "duplicate cross-cohort task",
                )
            seen_ids.add(instance_id)
            for kind, value in _candidate_fingerprint_items(candidate):
                kind_seen = seen_fingerprints.setdefault(kind, set())
                if value in kind_seen:
                    _fail(
                        f"{path}.candidate_report.candidates[{candidate_index}].fingerprints.{kind}",
                        "duplicate cross-cohort fingerprint",
                    )
                kind_seen.add(value)
    if len(seen_ids) != 456:
        _fail("plan.cohorts", "must freeze exactly 456 disjoint task IDs")
    return {
        "plan_id": obj["plan_id"],
        "candidates": 456,
        "development_max": 432,
        "looks": 3,
    }


def build_training_exclusion_registry(
    plan: Mapping[str, Any],
    base_registry: Mapping[str, Any],
    qualified_locks: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the complete evaluation-to-training exclusion registry.

    The call is the training-selection gate: it fails until all four qualified
    locks exist, validate against the pre-plan registry, and match the frozen
    candidate IDs and public fingerprints.  The resulting registry includes
    every task identity, repository/source identity, image cluster, and all six
    lock fingerprints, including the qualification-time AST fingerprint.
    """

    validate_sequential_plan(plan)
    validate_registry(base_registry)
    if plan["selection"]["base_exclusion_registry_sha256"] != _canonical_sha256(
        base_registry
    ):
        _fail(
            "base_registry", "does not match the exclusion registry frozen in the plan"
        )
    expected_ids = {cohort["cohort_id"] for cohort in plan["cohorts"]}
    if set(qualified_locks) != expected_ids:
        _fail("qualified_locks", f"must contain exactly {sorted(expected_ids)}")

    result = deepcopy(base_registry)
    result["registry_id"] = f"{plan['plan_id']}-training-exclusions"
    existing = {
        (entry["kind"], entry["value"].casefold()) for entry in result["entries"]
    }
    for cohort in plan["cohorts"]:
        cohort_id = cohort["cohort_id"]
        lock = qualified_locks[cohort_id]
        validate_lock(lock, base_registry)
        if lock["cohort_id"] != cohort_id:
            _fail(
                f"qualified_locks.{cohort_id}.cohort_id",
                "must match the frozen cohort ID",
            )
        if lock["selection"]["seed"] != cohort["seed"]:
            _fail(
                f"qualified_locks.{cohort_id}.selection.seed",
                "must match the frozen seed",
            )
        candidates = cohort["candidate_report"]["candidates"]
        if [task["instance_id"] for task in lock["tasks"]] != [
            row["instance_id"] for row in candidates
        ]:
            _fail(
                f"qualified_locks.{cohort_id}.tasks",
                "task IDs/order must match the frozen candidates",
            )
        for index, (task, candidate) in enumerate(zip(lock["tasks"], candidates)):
            for kind, value in _candidate_fingerprint_items(candidate):
                if task["fingerprints"][kind] != value:
                    _fail(
                        f"qualified_locks.{cohort_id}.tasks[{index}].fingerprints.{kind}",
                        "does not match the frozen candidate fingerprint",
                    )

        source = f"qualified-lock:{cohort_id}"
        result["source_digests"].append(
            {"name": source, "sha256": _canonical_sha256(lock)}
        )
        for task in lock["tasks"]:
            repo = task["repo"].casefold()
            identity = task["source_identity"]
            additions = [
                ("instance_id", task["instance_id"]),
                ("repo", repo),
                ("repo_pr", f"{repo}#{identity['pr_number']}"),
                ("base_commit", task["base_commit"]),
                ("merge_commit", identity["merge_commit"]),
            ]
            for issue_url in identity["issue_urls"]:
                additions.append(
                    (
                        "repo_issue",
                        f"{repo}#{int(issue_url.rstrip('/').rsplit('/', 1)[1])}",
                    )
                )
            additions.extend(
                ("episode_id", episode) for episode in identity["episode_ids"]
            )
            additions.extend(sorted(task["fingerprints"].items()))
            for kind, value in additions:
                key = (kind, value.casefold())
                if key not in existing:
                    result["entries"].append(
                        {"kind": kind, "value": value, "source": source}
                    )
                    existing.add(key)
    validate_registry(result)
    return result


def finalize_execution_freeze(
    plan: Mapping[str, Any],
    base_registry: Mapping[str, Any],
    qualified_locks: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind qualified locks, exclusions, hashes and order before formal outcomes.

    Returns ``(execution_freeze, training_exclusion_registry)``.  The caller
    persists both canonical JSON values before any formal model outcome exists.
    ``assess_look`` refuses outcomes that do not bind the resulting manifest.
    """

    validate_sequential_plan(plan)
    training_registry = build_training_exclusion_registry(
        plan, base_registry, qualified_locks
    )
    all_ids = [
        candidate["instance_id"]
        for cohort in plan["cohorts"]
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    development_ids = [
        candidate["instance_id"]
        for cohort in plan["cohorts"]
        if cohort["look_index"] > 0
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    execution_freeze = {
        "schema_version": EXECUTION_FREEZE_SCHEMA,
        "candidate_plan_sha256": _canonical_sha256(plan),
        "status": "frozen_before_formal_outcomes",
        "qualified_lock_sha256": {
            cohort["cohort_id"]: _canonical_sha256(qualified_locks[cohort["cohort_id"]])
            for cohort in plan["cohorts"]
        },
        "training_exclusion_registry_sha256": _canonical_sha256(training_registry),
        "ordered_all_instance_ids_sha256": _canonical_sha256(all_ids),
        "ordered_development_instance_ids_sha256": _canonical_sha256(development_ids),
        "formal_outcomes_may_begin": True,
    }
    validate_execution_freeze(plan, execution_freeze)
    return execution_freeze, training_registry


def validate_execution_freeze(
    plan: Mapping[str, Any], execution_freeze: Any
) -> dict[str, Any]:
    """Validate the pre-outcome hash manifest against the frozen candidate plan."""

    validate_sequential_plan(plan)
    obj = _object(execution_freeze, "execution_freeze", EXECUTION_FREEZE_KEYS)
    if obj["schema_version"] != EXECUTION_FREEZE_SCHEMA:
        _fail(
            "execution_freeze.schema_version", f"must equal {EXECUTION_FREEZE_SCHEMA!r}"
        )
    if obj["candidate_plan_sha256"] != _canonical_sha256(plan):
        _fail(
            "execution_freeze.candidate_plan_sha256", "does not bind the candidate plan"
        )
    if (
        obj["status"] != "frozen_before_formal_outcomes"
        or obj["formal_outcomes_may_begin"] is not True
    ):
        _fail("execution_freeze.status", "must be finalized before formal outcomes")
    lock_hashes = obj["qualified_lock_sha256"]
    expected_cohorts = [cohort["cohort_id"] for cohort in plan["cohorts"]]
    if not isinstance(lock_hashes, dict) or set(lock_hashes) != set(expected_cohorts):
        _fail(
            "execution_freeze.qualified_lock_sha256",
            "must bind exactly all four qualified locks",
        )
    for cohort_id, digest in lock_hashes.items():
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            _fail(
                f"execution_freeze.qualified_lock_sha256.{cohort_id}",
                "must be a lowercase SHA-256",
            )
    for field in (
        "training_exclusion_registry_sha256",
        "ordered_all_instance_ids_sha256",
        "ordered_development_instance_ids_sha256",
    ):
        digest = obj[field]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            _fail(f"execution_freeze.{field}", "must be a lowercase SHA-256")
    all_ids = [
        candidate["instance_id"]
        for cohort in plan["cohorts"]
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    development_ids = [
        candidate["instance_id"]
        for cohort in plan["cohorts"]
        if cohort["look_index"] > 0
        for candidate in cohort["candidate_report"]["candidates"]
    ]
    if obj["ordered_all_instance_ids_sha256"] != _canonical_sha256(all_ids):
        _fail(
            "execution_freeze.ordered_all_instance_ids_sha256",
            "does not bind all 456 ordered IDs",
        )
    if obj["ordered_development_instance_ids_sha256"] != _canonical_sha256(
        development_ids
    ):
        _fail(
            "execution_freeze.ordered_development_instance_ids_sha256",
            "does not bind all 432 ordered development IDs",
        )
    return {"qualified_locks": 4, "all_candidates": 456, "development_candidates": 432}


@cache
def exact_one_sided_mcnemar(v2_wins: int, base_wins: int) -> float:
    """P[X >= v2_wins] for X~Binomial(v2_wins+base_wins, 0.5)."""

    if min(v2_wins, base_wins) < 0:
        raise ValueError("discordant counts must be non-negative")
    discordant = v2_wins + base_wins
    if discordant == 0:
        return 1.0
    numerator = sum(
        math.comb(discordant, value) for value in range(v2_wins, discordant + 1)
    )
    return numerator / (2**discordant)


def _binomial_lower_tail(successes: int, trials: int, probability: float) -> float:
    if trials < 0 or not 0 <= successes <= trials or not 0.0 <= probability <= 1.0:
        raise ValueError("invalid binomial parameters")
    return sum(
        math.comb(trials, value)
        * (probability**value)
        * ((1.0 - probability) ** (trials - value))
        for value in range(successes + 1)
    )


def _clopper_pearson_lower(
    successes: int, trials: int, tail_probability: float
) -> float:
    """One-sided exact lower confidence bound for a binomial probability."""

    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("successes must be within a positive number of trials")
    if not 0.0 < tail_probability < 1.0:
        raise ValueError("tail_probability must be between zero and one")
    if successes == 0:
        return 0.0
    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2.0
        survival = 1.0 - _binomial_lower_tail(successes - 1, trials, mid)
        if survival < tail_probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _clopper_pearson_upper(
    successes: int, trials: int, tail_probability: float
) -> float:
    """One-sided exact upper confidence bound for a binomial probability."""

    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("successes must be within a positive number of trials")
    if not 0.0 < tail_probability < 1.0:
        raise ValueError("tail_probability must be between zero and one")
    if successes == trials:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2.0
        if _binomial_lower_tail(successes, trials, mid) > tail_probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def paired_risk_difference_upper_bound(
    v2_only_malformed: int,
    base_only_malformed: int,
    n: int,
    *,
    confidence: float = 0.95,
) -> float:
    """Conservative exact upper bound for paired malformed-risk difference.

    ``U/N`` and ``V/N`` are marginal multinomial-cell probabilities for v2-only
    and base-only malformed responses.  One-sided Clopper-Pearson bounds use a
    Bonferroni split of the total tail probability, so ``upper(U/N)-lower(V/N)``
    has simultaneous coverage of at least ``confidence`` despite dependence
    between the mutually exclusive paired cells.
    """

    if (
        n <= 0
        or min(v2_only_malformed, base_only_malformed) < 0
        or v2_only_malformed + base_only_malformed > n
    ):
        raise ValueError("discordant malformed counts must fit within a positive n")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between zero and one")
    marginal_tail = (1.0 - confidence) / 2.0
    return _clopper_pearson_upper(
        v2_only_malformed, n, marginal_tail
    ) - _clopper_pearson_lower(base_only_malformed, n, marginal_tail)


def _efficacy_crossed(v2_wins: int, base_wins: int, n: int, alpha: float) -> bool:
    return (
        exact_one_sided_mcnemar(v2_wins, base_wins) <= alpha
        and (v2_wins - base_wins) / n >= 0.05
    )


@lru_cache(maxsize=256)
def conditional_power(v2_wins: int, base_wins: int, n: int) -> float:
    """Exact fixed-alternative probability of a later preregistered crossing.

    The preregistered future per-task probabilities are 0.215 for a v2-only
    resolution, 0.135 for a base-only resolution, and 0.65 for a tie.  They
    correspond to delta*=0.08 and discordance s*=0.35.  Crossing states are
    removed at each future look because the protocol stops at first efficacy.
    """

    if n not in {144, 288}:
        raise ValueError(
            "conditional power is defined only at interim looks 144 and 288"
        )
    states: dict[tuple[int, int], float] = {(v2_wins, base_wins): 1.0}
    current_n = n
    crossing_probability = 0.0
    for spec in COHORT_SPECS[1:]:
        target_n = spec["cumulative_n"]
        if target_n <= current_n:
            continue
        for _ in range(target_n - current_n):
            advanced: defaultdict[tuple[int, int], float] = defaultdict(float)
            for (wins, losses), probability in states.items():
                advanced[(wins + 1, losses)] += probability * 0.215
                advanced[(wins, losses + 1)] += probability * 0.135
                advanced[(wins, losses)] += probability * 0.65
            states = dict(advanced)
        survivors: dict[tuple[int, int], float] = {}
        for (wins, losses), probability in states.items():
            if _efficacy_crossed(wins, losses, target_n, spec["alpha"]):
                crossing_probability += probability
            else:
                survivors[(wins, losses)] = probability
        states = survivors
        current_n = target_n
    return min(1.0, max(0.0, crossing_probability))


def _expected_outcome_ids(plan: Mapping[str, Any], look_index: int) -> dict[str, str]:
    expected: dict[str, str] = {}
    for cohort in plan["cohorts"]:
        if 1 <= cohort["look_index"] <= look_index:
            for candidate in cohort["candidate_report"]["candidates"]:
                expected[candidate["instance_id"]] = cohort["cohort_id"]
    return expected


def assess_look(
    plan: Mapping[str, Any],
    execution_freeze: Mapping[str, Any],
    outcomes: Mapping[str, Any],
) -> dict[str, Any]:
    """Assess one preregistered cumulative look without optional sample growth."""

    validate_sequential_plan(plan)
    validate_execution_freeze(plan, execution_freeze)
    obj = _object(outcomes, "outcomes", OUTCOMES_KEYS)
    if obj["schema_version"] != OUTCOMES_SCHEMA:
        _fail("outcomes.schema_version", f"must equal {OUTCOMES_SCHEMA!r}")
    if obj["plan_sha256"] != _canonical_sha256(plan):
        _fail("outcomes.plan_sha256", "does not bind the exact frozen plan")
    if obj["execution_freeze_sha256"] != _canonical_sha256(execution_freeze):
        _fail(
            "outcomes.execution_freeze_sha256",
            "does not bind the pre-outcome execution freeze",
        )
    look_index = _integer(obj["look_index"], "outcomes.look_index", 1)
    if look_index not in {1, 2, 3}:
        _fail(
            "outcomes.look_index", "may only be 1, 2, or 3; a fourth look is forbidden"
        )
    expected = _expected_outcome_ids(plan, look_index)
    records = obj["records"]
    if not isinstance(records, list):
        _fail("outcomes.records", "must be an array")
    if len(records) != len(expected):
        _fail(
            "outcomes.records",
            f"must contain exactly the cumulative {len(expected)} tasks",
        )

    by_id: dict[str, Mapping[str, Any]] = {}
    safety_events: list[dict[str, str]] = []
    for index, raw in enumerate(records):
        path = f"outcomes.records[{index}]"
        record = _object(raw, path, OUTCOME_RECORD_KEYS)
        instance_id = _nonempty(record["instance_id"], f"{path}.instance_id")
        if instance_id in by_id:
            _fail(f"{path}.instance_id", "duplicate task result")
        if instance_id not in expected:
            _fail(f"{path}.instance_id", "is not in the frozen cumulative look")
        if record["cohort_id"] != expected[instance_id]:
            _fail(f"{path}.cohort_id", "does not match the frozen cohort")
        arms = record["arms"]
        if not isinstance(arms, dict) or set(arms) != set(ARMS):
            _fail(f"{path}.arms", f"must contain exactly {list(ARMS)}")
        for arm_name in ARMS:
            arm = _object(arms[arm_name], f"{path}.arms.{arm_name}", ARM_RESULT_KEYS)
            for field in ARM_RESULT_KEYS:
                if not isinstance(arm[field], bool):
                    _fail(f"{path}.arms.{arm_name}.{field}", "must be boolean")
            for field in (
                "tamper_detected",
                "policy_violation",
                "isolation_violation",
                "receipt_inconsistent",
            ):
                if arm[field]:
                    safety_events.append(
                        {"instance_id": instance_id, "arm": arm_name, "field": field}
                    )
        by_id[instance_id] = record
    missing = sorted(set(expected) - set(by_id))
    if missing:
        _fail("outcomes.records", f"missing frozen task IDs: {missing[:3]}")

    ordered = [by_id[instance_id] for instance_id in expected]
    n = len(ordered)
    base_resolved = sum(row["arms"]["base"]["resolved"] for row in ordered)
    v1_resolved = sum(row["arms"]["v1"]["resolved"] for row in ordered)
    v2_resolved = sum(row["arms"]["v2"]["resolved"] for row in ordered)
    v2_wins = sum(
        row["arms"]["v2"]["resolved"] and not row["arms"]["base"]["resolved"]
        for row in ordered
    )
    base_wins = sum(
        row["arms"]["base"]["resolved"] and not row["arms"]["v2"]["resolved"]
        for row in ordered
    )
    p_value = exact_one_sided_mcnemar(v2_wins, base_wins)
    uplift = (v2_resolved - base_resolved) / n
    alpha = COHORT_SPECS[look_index]["alpha"]

    local_p_values = []
    for prior_look in range(1, look_index + 1):
        prior_n = COHORT_SPECS[prior_look]["cumulative_n"]
        prefix = ordered[:prior_n]
        prefix_wins = sum(
            row["arms"]["v2"]["resolved"] and not row["arms"]["base"]["resolved"]
            for row in prefix
        )
        prefix_losses = sum(
            row["arms"]["base"]["resolved"] and not row["arms"]["v2"]["resolved"]
            for row in prefix
        )
        local_p_values.append(exact_one_sided_mcnemar(prefix_wins, prefix_losses))
    weights = (0.20, 0.30, 0.50)
    sequential_adjusted_p = min(
        1.0,
        *(value / weights[index] for index, value in enumerate(local_p_values)),
    )

    base_malformed = sum(row["arms"]["base"]["malformed_response"] for row in ordered)
    v2_malformed = sum(row["arms"]["v2"]["malformed_response"] for row in ordered)
    malformed_u = sum(
        row["arms"]["v2"]["malformed_response"]
        and not row["arms"]["base"]["malformed_response"]
        for row in ordered
    )
    malformed_v = sum(
        row["arms"]["base"]["malformed_response"]
        and not row["arms"]["v2"]["malformed_response"]
        for row in ordered
    )
    malformed_discordant = malformed_u + malformed_v
    malformed_excess = (malformed_u - malformed_v) / n
    malformed_risk_difference_upper = paired_risk_difference_upper_bound(
        malformed_u, malformed_v, n
    )
    malformed_noninferior = malformed_risk_difference_upper <= 0.05
    malformed_harm_p = exact_one_sided_mcnemar(malformed_u, malformed_v)
    interim_harm = (
        look_index in {1, 2} and malformed_excess >= 0.05 and malformed_harm_p <= 0.005
    )
    efficacy = p_value <= alpha and uplift >= 0.05

    impossible = look_index in {1, 2} and (v2_wins - base_wins + (432 - n)) < 22
    power = conditional_power(v2_wins, base_wins, n) if look_index in {1, 2} else None
    futility = look_index in {1, 2} and (
        impossible or (power is not None and power < 0.10)
    )

    if safety_events or interim_harm:
        decision = "stop_safety_failure"
    elif efficacy and malformed_noninferior:
        decision = "stop_promote_to_final_holdout_decision"
    elif futility:
        decision = "stop_nonbinding_futility"
    elif look_index < 3:
        decision = "continue_to_next_preregistered_cohort"
    elif efficacy and not malformed_noninferior:
        decision = "stop_no_promotion_malformed_noninferiority_not_met"
    else:
        decision = "stop_no_promotion_at_maximum_n"

    return {
        "schema_version": "mini-gibson-sequential-development-assessment/v1",
        "plan_sha256": obj["plan_sha256"],
        "look_index": look_index,
        "cumulative_n": n,
        "alpha": alpha,
        "familywise_alpha_allocated_through_look": sum(
            spec["alpha"] for spec in COHORT_SPECS[1 : look_index + 1]
        ),
        "primary": {
            "base_resolved": base_resolved,
            "v2_resolved": v2_resolved,
            "v2_wins": v2_wins,
            "base_wins": base_wins,
            "absolute_uplift": uplift,
            "p_value_one_sided_exact_mcnemar": p_value,
            "local_bonferroni_weight": weights[look_index - 1],
            "local_p_values_through_look": local_p_values,
            "sequential_adjusted_p": sequential_adjusted_p,
            "minimum_absolute_uplift_met": uplift >= 0.05,
            "alpha_crossed": p_value <= alpha,
        },
        "secondary_descriptive": {
            "v1_resolved": v1_resolved,
            "v1_rate": v1_resolved / n,
        },
        "safety": {
            "integrity_events": safety_events,
            "base_malformed": base_malformed,
            "v2_malformed": v2_malformed,
            "malformed_u_v2_only": malformed_u,
            "malformed_v_base_only": malformed_v,
            "malformed_discordant": malformed_discordant,
            "malformed_observed_excess": malformed_excess,
            "malformed_risk_difference_upper_95": malformed_risk_difference_upper,
            "malformed_noninferiority_margin": 0.05,
            "malformed_noninferiority_method": (
                "simultaneous_marginal_clopper_pearson_bonferroni"
            ),
            "malformed_noninferiority_met": malformed_noninferior,
            "interim_harm_p_one_sided_exact_mcnemar": malformed_harm_p,
            "interim_harm_stop": interim_harm,
        },
        "futility": {
            "nonbinding": True,
            "mathematically_impossible_to_reach_22_net_wins": impossible,
            "conditional_power_fixed_alternative": power,
            "conditional_power_below_0_10": power is not None and power < 0.10,
            "stop": futility,
            "override_requires_reported_protocol_deviation": True,
        },
        "decision": decision,
        "final_holdout_opened": False,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze", help="freeze all four candidate manifests")
    freeze.add_argument("--records", type=Path, required=True)
    freeze.add_argument("--registry", type=Path, required=True)
    freeze.add_argument("--plan-id", required=True)
    freeze.add_argument("--master-seed", type=int, default=414)
    freeze.add_argument("--output", type=Path, required=True)
    assess = subparsers.add_parser("assess", help="assess one fixed cumulative look")
    assess.add_argument("--plan", type=Path, required=True)
    assess.add_argument("--execution-freeze", type=Path, required=True)
    assess.add_argument("--outcomes", type=Path, required=True)
    assess.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        value = freeze_sequential_plan(
            _load_jsonl(args.records),
            _load_json(args.registry),
            plan_id=args.plan_id,
            master_seed=args.master_seed,
        )
    else:
        value = assess_look(
            _load_json(args.plan),
            _load_json(args.execution_freeze),
            _load_json(args.outcomes),
        )
    args.output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
