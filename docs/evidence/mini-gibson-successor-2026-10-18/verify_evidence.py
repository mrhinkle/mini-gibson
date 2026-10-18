#!/usr/bin/env python3
"""Verify the public terminal Mini-Gibson R3 evidence package."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.preflight_candidates import (  # noqa: E402
    HEADER_KEYS,
    JOURNAL_SCHEMA,
    MANIFEST_SCHEMA,
    PREDECESSOR_TERMINAL_RECEIPT_SHA256,
    RECORD_KEYS,
    _candidate_sequence,
)
from evaluation.sequential import (  # noqa: E402
    canonical_plan_sha256,
    validate_sequential_plan,
)
from evaluation.qualify_candidates import (  # noqa: E402
    DATASET_REVISION,
    FROZEN_EVIDENCE_FILE_SHA256,
    FROZEN_PLAN_CANONICAL_SHA256,
    FROZEN_PLAN_FILE_SHA256,
    FROZEN_REGISTRY_CANONICAL_SHA256,
    FROZEN_REGISTRY_FILE_SHA256,
    SOURCE_SHA256,
    _canonical_sha256,
)
from evaluation.verify_rebench import (  # noqa: E402
    PREFLIGHT_RECEIPT_SCHEMA,
    verify_preflight_receipt,
)


SOURCE_COMMIT = "954d6e7290f51b29f5b5b30c2ba00b2556d4fdca"
EXPECTED_CANDIDATES = 456
EXPECTED_STATE = "preflight_complete_incompatible"
EXPECTED_HOLDOUT = "sealed_not_read_or_run"
EXPECTED_HOURLY_RATE = 3.96
HOURLY_CAP = 30.0
ZERO_SHA256 = "0" * 64
SHA256_RE = re.compile(r"[0-9a-f]{64}")
FROZEN = REPOSITORY_ROOT / "evaluation/frozen/mini-gibson-v2-sequential-2026-10-17"
EXPECTED_PACKAGE_FILES = (
    "LIMITATIONS.md",
    "REPORT.md",
    "compatibility/STATUS.public.json",
    "compatibility/bindings.json",
    "compatibility/compatibility-manifest.json",
    "compatibility/compatibility-preflight.jsonl",
    "compatibility/matrix.json",
    "cost.json",
    "summary.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name}: expected a JSON object")
    return value


def iso(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def verify_inventory() -> None:
    sums_path = ROOT / "SHA256SUMS"
    if not sums_path.is_file() or sums_path.is_symlink():
        raise SystemExit("terminal evidence package is incomplete: SHA256SUMS is missing")
    lines = sums_path.read_text(encoding="utf-8").splitlines()
    records: list[tuple[str, str]] = []
    for line in lines:
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise SystemExit("SHA256SUMS contains a malformed line") from exc
        pure = PurePosixPath(relative)
        if (
            not SHA256_RE.fullmatch(digest)
            or pure.is_absolute()
            or ".." in pure.parts
            or pure.as_posix() != relative
        ):
            raise SystemExit(f"SHA256SUMS contains an unsafe entry: {relative!r}")
        records.append((digest, relative))
    relatives = [relative for _, relative in records]
    if relatives != sorted(EXPECTED_PACKAGE_FILES) or len(set(relatives)) != len(relatives):
        raise SystemExit("SHA256SUMS does not exactly cover the public package")
    for expected, relative in records:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise SystemExit(f"hash mismatch or unsafe file: {relative}")


def load_journal(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        raise SystemExit("journal has an incomplete final record")
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != EXPECTED_CANDIDATES + 1:
        raise SystemExit("journal is not the complete 456-receipt matrix")
    previous = ZERO_SHA256
    for sequence, row in enumerate(rows):
        expected_keys = HEADER_KEYS if sequence == 0 else RECORD_KEYS
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise SystemExit(f"journal fields differ at sequence {sequence}")
        body = dict(row)
        record_hash = body.pop("record_sha256", None)
        if (
            row.get("schema_version") != JOURNAL_SCHEMA
            or row.get("sequence") != sequence
            or row.get("previous_record_sha256") != previous
            or record_hash != canonical_sha256(body)
        ):
            raise SystemExit(f"journal chain fails at sequence {sequence}")
        if sequence == 0:
            if row.get("record_type") != "header":
                raise SystemExit("journal header record type changed")
        else:
            receipt = row.get("receipt")
            if (
                row.get("record_type") != "compatibility_receipt"
                or receipt.get("schema_version") != PREFLIGHT_RECEIPT_SCHEMA
                or receipt.get("instance_id") != row.get("instance_id")
                or not verify_preflight_receipt(receipt)
            ):
                raise SystemExit(f"R3/v2 receipt verification fails at {sequence}")
        previous = str(record_hash)
    return rows


def classify(receipt: Mapping[str, Any]) -> str:
    if receipt["compatible"]:
        return "compatible"
    precheck = receipt.get("precheck_error")
    if precheck is not None:
        if str(precheck).startswith("product patch touches protected test paths:"):
            return "gold_patch_touches_protected_test_path"
        return "patch_policy_precheck_failed"
    codes = tuple(sorted({int(run["returncode"]) for run in receipt["runs"]}))
    known = {
        (82,): "image_workdir_unavailable",
        (83,): "image_workdir_not_git_checkout",
        (84,): "git_status_precheck_failed",
        (85,): "gold_patch_precheck_failed",
        (86,): "gold_patch_application_failed",
        (87,): "test_patch_precheck_failed",
        (88,): "test_patch_application_failed",
        (92,): "tracked_file_enumeration_failed",
        (93,): "protected_path_discovery_failed",
        (94,): "protected_path_input_invalid",
        (95,): "protected_path_finalize_failed",
        (96,): "git_head_resolution_failed",
        (97,): "protected_test_paths_changed",
        (98,): "image_head_mismatch",
        (99,): "dirty_image_checkout_before_patching",
    }
    return known.get(codes, "mixed_mechanics_failure_" + "_".join(map(str, codes)))


def expected_matrix(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter, Counter]:
    matrix: list[dict[str, Any]] = []
    classifications: Counter = Counter()
    cohorts: Counter = Counter()
    for row in rows:
        receipt = row["receipt"]
        runs = {run["phase"]: run for run in receipt["runs"]}
        classification = classify(receipt)
        classifications[classification] += 1
        cohorts[row["cohort_id"]] += 1
        matrix.append(
            {
                "sequence": row["sequence"],
                "cohort_id": row["cohort_id"],
                "selection_rank": row["selection_rank"],
                "instance_id": row["instance_id"],
                "input_sha256": row["input_sha256"],
                "record_sha256": row["record_sha256"],
                "receipt_sha256": receipt["receipt_sha256"],
                "compatible": receipt["compatible"],
                "execution_path": (
                    "host_policy_precheck"
                    if receipt.get("precheck_error") is not None
                    else "networkless_verifier_containers"
                ),
                "base_compatible": runs.get("base", {}).get("compatible"),
                "base_returncode": runs.get("base", {}).get("returncode"),
                "gold_compatible": runs.get("gold", {}).get("compatible"),
                "gold_returncode": runs.get("gold", {}).get("returncode"),
                "classification": classification,
            }
        )
    return matrix, classifications, cohorts


def main() -> int:
    verify_inventory()
    plan_path = FROZEN / "sequential-plan.json"
    registry_path = FROZEN / "pre-plan-exclusions.json"
    evidence_path = FROZEN / "freeze-evidence.json"
    plan = read_json(plan_path)
    registry = read_json(registry_path)
    validate_sequential_plan(plan)
    if (
        canonical_plan_sha256(plan) != FROZEN_PLAN_CANONICAL_SHA256
        or sha256(plan_path) != FROZEN_PLAN_FILE_SHA256
        or _canonical_sha256(registry) != FROZEN_REGISTRY_CANONICAL_SHA256
        or sha256(registry_path) != FROZEN_REGISTRY_FILE_SHA256
        or sha256(evidence_path) != FROZEN_EVIDENCE_FILE_SHA256
    ):
        raise SystemExit("committed frozen-authority hashes differ")
    sequence = _candidate_sequence(plan)
    if len(sequence) != EXPECTED_CANDIDATES:
        raise SystemExit("committed plan is not the frozen 456-task cohort")

    journal_path = ROOT / "compatibility/compatibility-preflight.jsonl"
    manifest_path = ROOT / "compatibility/compatibility-manifest.json"
    rows = load_journal(journal_path)
    header = rows[0]
    receipts = rows[1:]
    invariants = header["invariants"]
    invariant_keys = {
        "candidate_plan_sha256",
        "candidate_plan_file_sha256",
        "base_exclusion_registry_canonical_sha256",
        "base_exclusion_registry_file_sha256",
        "freeze_evidence_file_sha256",
        "dataset_revision",
        "dataset_sha256",
        "material_package_sha256",
        "image_lock_sha256",
        "parser_source_sha256",
        "verifier_package_sha256",
        "tooling",
        "ordered_instance_ids_sha256",
        "candidate_count",
        "final_holdout_status",
        "preflight_module_sha256",
        "preflight_controller_sha256",
        "predecessor_experiment",
        "predecessor_terminal_receipt_sha256",
        "preflight_scope",
        "formal_model_outcomes_observed",
    }
    if not isinstance(invariants, dict) or set(invariants) != invariant_keys:
        raise SystemExit("journal invariant fields changed")
    tooling_expected = {
        "orchestrator_sha256": sha256(REPOSITORY_ROOT / "evaluation/qualify_candidates.py"),
        "docker_backend_sha256": sha256(REPOSITORY_ROOT / "evaluation/docker_backend.py"),
        "verifier_sha256": sha256(REPOSITORY_ROOT / "evaluation/verify_rebench.py"),
        "cohort_validator_sha256": sha256(REPOSITORY_ROOT / "evaluation/cohort.py"),
    }
    parser_hashes = invariants.get("parser_source_sha256")
    if (
        invariants["candidate_plan_sha256"] != FROZEN_PLAN_CANONICAL_SHA256
        or invariants["candidate_plan_file_sha256"] != FROZEN_PLAN_FILE_SHA256
        or invariants["base_exclusion_registry_canonical_sha256"]
        != FROZEN_REGISTRY_CANONICAL_SHA256
        or invariants["base_exclusion_registry_file_sha256"]
        != FROZEN_REGISTRY_FILE_SHA256
        or invariants["freeze_evidence_file_sha256"] != FROZEN_EVIDENCE_FILE_SHA256
        or invariants["dataset_revision"] != DATASET_REVISION
        or invariants["dataset_sha256"] != SOURCE_SHA256
        or invariants["verifier_package_sha256"]
        != invariants["material_package_sha256"]
        or invariants["tooling"] != tooling_expected
        or invariants["preflight_module_sha256"]
        != sha256(REPOSITORY_ROOT / "evaluation/preflight_candidates.py")
        or invariants["preflight_controller_sha256"]
        != sha256(REPOSITORY_ROOT / "evaluation/preflight_controller.py")
        or invariants["ordered_instance_ids_sha256"]
        != _canonical_sha256([candidate["instance_id"] for _, candidate in sequence])
        or invariants["candidate_count"] != EXPECTED_CANDIDATES
        or invariants["final_holdout_status"] != EXPECTED_HOLDOUT
        or invariants["predecessor_experiment"] != "mini-gibson-v2-2026-10-18"
        or invariants["predecessor_terminal_receipt_sha256"]
        != PREDECESSOR_TERMINAL_RECEIPT_SHA256
        or invariants["preflight_scope"]
        != "all_456_candidates_base_and_gold_patch_mechanics_no_tests"
        or invariants["formal_model_outcomes_observed"] is not False
        or not isinstance(parser_hashes, dict)
        or not parser_hashes
        or any(not SHA256_RE.fullmatch(value) for value in parser_hashes.values())
    ):
        raise SystemExit("journal invariants do not bind the committed authority")

    bindings = read_json(ROOT / "compatibility/bindings.json")
    binding_rows = bindings.get("records")
    if (
        bindings.get("schema_version") != 1
        or bindings.get("source_commit") != SOURCE_COMMIT
        or bindings.get("candidate_plan_sha256") != FROZEN_PLAN_CANONICAL_SHA256
        or not isinstance(binding_rows, list)
        or len(binding_rows) != EXPECTED_CANDIDATES
    ):
        raise SystemExit("binding manifest metadata changed")
    for index, ((cohort_id, candidate), row, binding) in enumerate(
        zip(sequence, receipts, binding_rows, strict=True), start=1
    ):
        if set(binding) != {
            "sequence",
            "cohort_id",
            "selection_rank",
            "instance_id",
            "input_sha256",
            "receipt_fields",
        }:
            raise SystemExit(f"binding fields differ at sequence {index}")
        expected_plan = {
            "sequence": index,
            "cohort_id": cohort_id,
            "selection_rank": candidate["selection_rank"],
            "instance_id": candidate["instance_id"],
            "input_sha256": row["input_sha256"],
        }
        if any(binding[key] != value for key, value in expected_plan.items()):
            raise SystemExit(f"frozen order binding fails at sequence {index}")
        receipt_fields = binding["receipt_fields"]
        expected_receipt_keys = {
            "instance_id",
            "base_commit",
            "image_reference",
            "image_digest",
            "workdir",
            "verify_timeout_s",
            "gold_patch_sha256",
            "test_patch_sha256",
            "test_command_sha256",
            "mechanics_command_sha256",
        }
        if (
            not isinstance(receipt_fields, dict)
            or set(receipt_fields) != expected_receipt_keys
            or receipt_fields["base_commit"] != candidate["base_commit"]
            or any(row["receipt"].get(key) != value for key, value in receipt_fields.items())
            or row["cohort_id"] != cohort_id
            or row["selection_rank"] != candidate["selection_rank"]
            or row["instance_id"] != candidate["instance_id"]
        ):
            raise SystemExit(f"receipt binding fails at sequence {index}")

    compatible = sum(bool(row["receipt"]["compatible"]) for row in receipts)
    incompatible = EXPECTED_CANDIDATES - compatible
    incompatible_ids = [
        row["instance_id"]
        for row in receipts
        if not row["receipt"]["compatible"]
    ]
    if incompatible < 1:
        raise SystemExit("terminal incompatible boundary was not reached")
    manifest = read_json(manifest_path)
    expected_manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "status": EXPECTED_STATE,
        "candidate_count": EXPECTED_CANDIDATES,
        "compatible_count": compatible,
        "incompatible_count": incompatible,
        "incompatible_instance_ids": incompatible_ids,
        "candidate_plan_sha256": invariants["candidate_plan_sha256"],
        "dataset_revision": invariants["dataset_revision"],
        "dataset_sha256": invariants["dataset_sha256"],
        "material_package_sha256": invariants["material_package_sha256"],
        "image_lock_sha256": invariants["image_lock_sha256"],
        "preflight_module_sha256": invariants["preflight_module_sha256"],
        "preflight_controller_sha256": invariants["preflight_controller_sha256"],
        "docker_backend_sha256": invariants["tooling"]["docker_backend_sha256"],
        "verifier_sha256": invariants["tooling"]["verifier_sha256"],
        "predecessor_terminal_receipt_sha256": PREDECESSOR_TERMINAL_RECEIPT_SHA256,
        "journal_sha256": sha256(journal_path),
        "journal_head_sha256": rows[-1]["record_sha256"],
        "formal_model_outcomes_observed": False,
        "final_holdout_status": EXPECTED_HOLDOUT,
    }
    if manifest != expected_manifest:
        raise SystemExit("terminal manifest disagrees with the bound journal")

    status = read_json(ROOT / "compatibility/STATUS.public.json")
    status_keys = {
        "schema_version",
        "source_commit",
        "state",
        "recorded",
        "compatible",
        "incompatible",
        "remaining",
        "current_instance_id",
        "journal_head_sha256",
        "manifest_sha256",
        "formal_model_outcomes_observed",
        "final_holdout_status",
        "hourly_rate_usd",
        "estimated_controller_window_cost_usd",
        "started_unix",
        "updated_unix",
        "rate_limit_retries",
    }
    if (
        set(status) != status_keys
        or status["source_commit"] != SOURCE_COMMIT
        or status["state"] != EXPECTED_STATE
        or status["recorded"] != EXPECTED_CANDIDATES
        or status["compatible"] != compatible
        or status["incompatible"] != incompatible
        or status["remaining"] != 0
        or status["current_instance_id"] is not None
        or status["journal_head_sha256"] != rows[-1]["record_sha256"]
        or status["manifest_sha256"] != sha256(manifest_path)
        or status["formal_model_outcomes_observed"] is not False
        or status["final_holdout_status"] != EXPECTED_HOLDOUT
        or status["hourly_rate_usd"] != EXPECTED_HOURLY_RATE
        or not isinstance(status["rate_limit_retries"], int)
        or status["rate_limit_retries"] < 0
    ):
        raise SystemExit("terminal status disagrees with the manifest")
    started = status["started_unix"]
    ended = status["updated_unix"]
    if not isinstance(started, int) or not isinstance(ended, int) or ended < started:
        raise SystemExit("controller timestamps are missing or inverted")
    hours = (ended - started) / 3600
    if abs(status["estimated_controller_window_cost_usd"] - round(hours * EXPECTED_HOURLY_RATE, 4)) > 0.01:
        raise SystemExit("controller cost does not reconcile")

    matrix, classifications, cohorts = expected_matrix(receipts)
    if read_json(ROOT / "compatibility/matrix.json") != {
        "schema_version": 1,
        "records": matrix,
    }:
        raise SystemExit("public matrix differs from the journal")

    expected_cost = {
        "schema_version": 1,
        "instance": "weird-white-ocelot",
        "instance_id": "ds7uiptfk",
        "instance_type": "a100-80gb.2x",
        "gpu_count": 2,
        "gpu_model": "NVIDIA A100 80GB PCIe",
        "hourly_rate_usd": EXPECTED_HOURLY_RATE,
        "approved_hourly_cap_usd": HOURLY_CAP,
        "controller_window_start": iso(started),
        "terminal_status_at": iso(ended),
        "controller_window_hours_estimate": round(hours, 4),
        "estimated_controller_window_cost_usd": status[
            "estimated_controller_window_cost_usd"
        ],
        "method": "controller start through terminal status timestamp multiplied by the live Brev hourly rate; reconciled to the controller status",
        "limitations": "This estimate covers only the R3 controller window. The instance remains running because stopping it requires fresh explicit confirmation, so charges continue after this evidence cutoff.",
    }
    cost = read_json(ROOT / "cost.json")
    if cost != expected_cost:
        raise SystemExit("cost record does not reconcile")

    expected_summary = {
        "schema_version": 1,
        "evidence_state": "terminal_successor_compatibility_preflight",
        "evidence_cutoff": iso(ended),
        "deliverable": "reproducible_training_and_evaluation_pipeline_not_a_production_model_release",
        "current_conclusion": "v1_promising_not_promotable_successor_cohort_incompatible_no_new_model_result",
        "v1": {
            "tasks": 48,
            "base_resolved": 9,
            "tuned_resolved": 16,
            "absolute_uplift": 0.14583333333333334,
            "tuned_only_wins": 12,
            "base_only_wins": 5,
            "one_sided_exact_p": 0.0717316,
            "base_tasks_with_malformed_response": 8,
            "tuned_tasks_with_malformed_response": 21,
            "malformed_task_incidence_p": 0.000488,
            "promotion": False,
        },
        "successor": {
            "status": EXPECTED_STATE,
            "candidate_count": EXPECTED_CANDIDATES,
            "recorded": EXPECTED_CANDIDATES,
            "compatible_count": compatible,
            "incompatible_count": incompatible,
            "incompatible_instance_ids": incompatible_ids,
            "classification_counts": dict(sorted(classifications.items())),
            "cohort_counts": dict(sorted(cohorts.items())),
            "models_run": 0,
            "agents_run": 0,
            "tests_run": 0,
            "training_started": False,
            "formal_development_n": 0,
            "formal_decision": "not_reached_preflight_incompatible",
            "final_holdout": "operationally_sealed_unconsumed",
        },
        "provenance": {
            "source_commit": SOURCE_COMMIT,
            "dataset_revision": manifest["dataset_revision"],
            "dataset_sha256": manifest["dataset_sha256"],
            "candidate_plan_sha256": manifest["candidate_plan_sha256"],
            "material_package_sha256": manifest["material_package_sha256"],
            "image_lock_sha256": manifest["image_lock_sha256"],
            "preflight_module_sha256": manifest["preflight_module_sha256"],
            "preflight_controller_sha256": manifest["preflight_controller_sha256"],
            "docker_backend_sha256": manifest["docker_backend_sha256"],
            "verifier_sha256": manifest["verifier_sha256"],
            "journal_sha256": sha256(journal_path),
            "journal_head_sha256": rows[-1]["record_sha256"],
            "manifest_sha256": sha256(manifest_path),
            "bindings_sha256": sha256(ROOT / "compatibility/bindings.json"),
        },
        "cost": expected_cost,
    }
    if read_json(ROOT / "summary.json") != expected_summary:
        raise SystemExit("summary differs from the verified evidence")

    report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
    limitations = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
    required_report = (
        f"**{compatible} compatible** packages and **{incompatible} incompatible** packages",
        "The public 35-task Gibson Bench final holdout remains operationally sealed",
        "It ran no model, agent, parser, or tests.",
    )
    if any(text not in report for text in required_report) or f"{incompatible} of {EXPECTED_CANDIDATES}" not in limitations:
        raise SystemExit("human-readable conclusion differs from the verified boundary")

    print(
        "successor evidence verification passed: "
        f"{compatible} compatible, {incompatible} incompatible, holdout operationally sealed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
