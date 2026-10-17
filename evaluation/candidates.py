"""Deterministic preselection for SWE-rebench V2 development candidates.

This module creates a *candidate report*, never a runnable cohort lock. Image
digests, sealed verifier material, AST fingerprints, and repeated qualification
receipts must be added by the later qualification lane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from .cohort import (
    DATASET,
    DATASET_REVISION,
    SELECTION_POLICY,
    SUPPORTED_LOG_PARSERS,
    validate_registry,
)


HIGH_RISK_LICENSES = {"", "unknown", "noassertion", "proprietary", "unlicensed"}
HIGH_RISK_TEXT = re.compile(
    r"\b(migrations?|database|postgres|mysql|mongodb|redis|credentials?|secrets?|"
    r"submodules?|production|terraform|kubernetes|aws|gcp|azure)\b",
    re.I,
)
BINARY_PATCH = re.compile(r"(^|\n)(GIT binary patch|Binary files .+ differ)(\n|$)")
DIFF_PATH = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.M)
NETWORK_OR_SERVICE_CMD = re.compile(
    r"\b(curl|wget|nc|ncat|ssh|scp|psql|mysql|mongosh|redis-cli|docker|kubectl|terraform)\b",
    re.I,
)


class CandidateSelectionError(ValueError):
    """Pinned records cannot satisfy the frozen candidate policy."""


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_json_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(rendered).hexdigest()


def _normalized_statement(value: str) -> str:
    return " ".join(value.casefold().split())


def _changed_files(patch: str) -> list[str]:
    return sorted({path for pair in DIFF_PATH.findall(patch) for path in pair})


def _github_pr_number(url: str) -> int | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    try:
        marker = parts.index("pull")
        return int(parts[marker + 1])
    except (ValueError, IndexError):
        return None


def _source_pr(record: Mapping[str, Any], meta: Mapping[str, Any]) -> tuple[str | None, int | None]:
    raw_url = meta.get("pr_url")
    if isinstance(raw_url, str):
        number = _github_pr_number(raw_url)
        if number is not None:
            return raw_url, number
    match = re.search(r"-(\d+)$", record["instance_id"])
    if match and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", record["repo"]):
        number = int(match.group(1))
        return f"https://github.com/{record['repo']}/pull/{number}", number
    return None, None


def _issue_urls(metadata: Mapping[str, Any]) -> list[str]:
    raw = metadata.get("external_urls", [])
    if not isinstance(raw, list):
        return []
    result = []
    for url in raw:
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.casefold() == "github.com" and "issues" in parts:
            result.append(url)
    return sorted(set(result))


def _rename_only(patch: str) -> bool:
    changed = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            changed.append(line)
    return bool(patch.strip()) and not changed and "rename from " in patch and "rename to " in patch


def _eligibility(record: Mapping[str, Any]) -> tuple[list[str], dict[str, Any] | None]:
    reasons: list[str] = []
    required_strings = (
        "instance_id",
        "repo",
        "base_commit",
        "problem_statement",
        "image_name",
        "language",
        "license",
        "patch",
        "test_patch",
    )
    for name in required_strings:
        if not isinstance(record.get(name), str) or not record[name].strip():
            reasons.append(f"missing_{name}")
    if reasons:
        return sorted(set(reasons)), None

    if not re.fullmatch(r"[0-9a-f]{40}", record["base_commit"]):
        reasons.append("invalid_base_commit")
    if not isinstance(record.get("FAIL_TO_PASS"), list) or not record["FAIL_TO_PASS"]:
        reasons.append("missing_fail_to_pass")

    install = record.get("install_config")
    if not isinstance(install, dict):
        reasons.append("missing_install_config")
        install = {}
    parser = install.get("log_parser")
    test_cmd = install.get("test_cmd")
    if parser not in SUPPORTED_LOG_PARSERS:
        reasons.append("unsupported_log_parser")
    if not isinstance(test_cmd, str) or not test_cmd.strip():
        reasons.append("missing_test_command")
    elif NETWORK_OR_SERVICE_CMD.search(test_cmd):
        reasons.append("network_or_service_test_command")

    license_name = record["license"].strip()
    if license_name.casefold() in HIGH_RISK_LICENSES:
        reasons.append("high_risk_license")
    patch = record["patch"]
    test_patch = record["test_patch"]
    if "\x00" in patch or "\x00" in test_patch or BINARY_PATCH.search(patch):
        reasons.append("binary_patch")
    if _rename_only(patch):
        reasons.append("rename_only")

    changed_files = _changed_files(patch)
    if not changed_files:
        reasons.append("no_changed_files")
    risky_paths = [
        path
        for path in changed_files
        if HIGH_RISK_TEXT.search(path) or path.endswith((".sql", ".pem", ".key", ".p12"))
    ]
    if risky_paths or HIGH_RISK_TEXT.search(record["problem_statement"]):
        reasons.append("high_risk_task_surface")

    meta = record.get("meta")
    if not isinstance(meta, dict):
        reasons.append("missing_meta")
        meta = {}
    llm = meta.get("llm_metadata")
    if not isinstance(llm, dict):
        reasons.append("missing_quality_metadata")
        llm = {}
    if llm.get("intent_completeness") != "complete":
        reasons.append("incomplete_intent")
    confidence = llm.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or confidence < 0.9:
        reasons.append("low_quality_confidence")
    if llm.get("code") != "A":
        reasons.append("quality_code_not_a")
    detected = llm.get("detected_issues")
    if isinstance(detected, dict) and any(detected.values()):
        reasons.append("quality_issue_detected")
    alignment = llm.get("test_alignment_issues")
    if isinstance(alignment, list) and alignment:
        reasons.append("test_alignment_issue")

    pr_url, pr_number = _source_pr(record, meta)
    if pr_number is None:
        reasons.append("missing_source_pr")
    if reasons:
        return sorted(set(reasons)), None

    issue_text_sha256 = _digest_text(_normalized_statement(record["problem_statement"]))
    patch_sha256 = _digest_text(patch)
    test_patch_sha256 = _digest_text(test_patch)
    changed_files_sha256 = _canonical_json_digest(changed_files)
    image_cluster_sha256 = _digest_text(f"{record['repo'].casefold()}\0{record['image_name']}")
    safe = {
        "instance_id": record["instance_id"],
        "repo": record["repo"],
        "base_commit": record["base_commit"],
        "image_name": record["image_name"],
        "language": record["language"].casefold(),
        "license": license_name,
        "source_pr_url": pr_url,
        "source_pr_number": pr_number,
        "source_issue_urls": _issue_urls(llm),
        "difficulty": llm.get("difficulty", "unknown"),
        "num_modified_files": meta.get("num_modified_files"),
        "num_modified_lines": meta.get("num_modified_lines"),
        "log_parser": parser,
        "install_config_sha256": _canonical_json_digest(install),
        "fingerprints": {
            "issue_text_sha256": issue_text_sha256,
            "patch_sha256": patch_sha256,
            "test_patch_sha256": test_patch_sha256,
            "changed_files_sha256": changed_files_sha256,
            "image_cluster_sha256": image_cluster_sha256,
        },
    }
    return [], safe


def _registry_overlap(candidate: Mapping[str, Any], exclusions: Mapping[str, set[str]]) -> str | None:
    values = {
        "instance_id": candidate["instance_id"].casefold(),
        "repo": candidate["repo"].casefold(),
        "repo_pr": f"{candidate['repo'].casefold()}#{candidate['source_pr_number']}",
        "base_commit": candidate["base_commit"].lower(),
        **{key: value.lower() for key, value in candidate["fingerprints"].items()},
    }
    for url in candidate["source_issue_urls"]:
        number = _github_pr_number(url.replace("/issues/", "/pull/"))
        if number is not None:
            values[f"repo_issue:{number}"] = f"{candidate['repo'].casefold()}#{number}"
    for key, value in values.items():
        kind = key.split(":", 1)[0]
        if value in exclusions.get(kind, set()):
            return kind
    return None


def _stable_key(candidate: Mapping[str, Any], seed: int) -> str:
    return _digest_text(f"{seed}\0{candidate['instance_id']}")


def _choose(
    candidates: Sequence[dict[str, Any]],
    *,
    target: int,
    min_languages: int,
    min_repositories: int,
    repo_cap: int,
    seed: int,
) -> list[dict[str, Any]]:
    ordered = sorted(candidates, key=lambda row: (_stable_key(row, seed), row["instance_id"]))
    by_language = Counter(row["language"] for row in ordered)
    languages = [name for name, _ in sorted(by_language.items(), key=lambda item: (-item[1], item[0]))]
    if len(languages) < min_languages:
        raise CandidateSelectionError("eligible records have insufficient language diversity")
    if len({row["repo"].casefold() for row in ordered}) < min_repositories:
        raise CandidateSelectionError("eligible records have insufficient repository diversity")

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    repo_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()

    def add(row: dict[str, Any]) -> bool:
        repo = row["repo"].casefold()
        if row["instance_id"] in selected_ids or repo_counts[repo] >= repo_cap:
            return False
        selected.append(row)
        selected_ids.add(row["instance_id"])
        repo_counts[repo] += 1
        language_counts[row["language"]] += 1
        difficulty_counts[row["difficulty"]] += 1
        return True

    for language in languages[:min_languages]:
        row = next((item for item in ordered if item["language"] == language and add(item)), None)
        if row is None:
            raise CandidateSelectionError(f"could not reserve language {language!r}")

    while len(repo_counts) < min_repositories:
        unselected = [row for row in ordered if row["instance_id"] not in selected_ids]
        unselected.sort(
            key=lambda row: (
                row["repo"].casefold() in repo_counts,
                language_counts[row["language"]],
                repo_counts[row["repo"].casefold()],
                _stable_key(row, seed),
            )
        )
        if not unselected or not add(unselected[0]):
            raise CandidateSelectionError("could not satisfy repository diversity")

    while len(selected) < target:
        choices = [
            row
            for row in ordered
            if row["instance_id"] not in selected_ids
            and repo_counts[row["repo"].casefold()] < repo_cap
        ]
        if not choices:
            raise CandidateSelectionError("eligible records cannot fill target under repository cap")
        choices.sort(
            key=lambda row: (
                language_counts[row["language"]],
                difficulty_counts[row["difficulty"]],
                repo_counts[row["repo"].casefold()],
                _stable_key(row, seed),
            )
        )
        add(choices[0])

    for rank, row in enumerate(selected, 1):
        row["selection_rank"] = rank
        row["selection_key"] = _stable_key(row, seed)
        row["qualification_status"] = "pending"
    return selected


def select_candidates(
    records: Iterable[Mapping[str, Any]],
    registry: Mapping[str, Any],
    *,
    mode: str,
    seed: int,
    target: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-runnable candidate report."""

    if mode not in {"pilot", "development"}:
        raise CandidateSelectionError("mode must be 'pilot' or 'development'")
    frozen_target = 24 if mode == "pilot" else 144
    if target is not None and target != frozen_target:
        raise CandidateSelectionError(f"target must equal frozen {mode} size {frozen_target}")
    min_languages, min_repositories, repo_cap = (6, 12, 4) if mode == "pilot" else (8, 24, 8)
    exclusions, registry_sources = validate_registry(registry)

    eligible: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    total = 0
    seen_ids: set[str] = set()
    for record in records:
        total += 1
        reasons, safe = _eligibility(record)
        if safe is not None and safe["instance_id"] in seen_ids:
            reasons.append("duplicate_instance_id")
            safe = None
        if safe is not None:
            overlap = _registry_overlap(safe, exclusions)
            if overlap:
                reasons.append(f"registry_overlap_{overlap}")
                safe = None
        if reasons:
            rejection_counts.update(set(reasons))
            continue
        assert safe is not None
        seen_ids.add(safe["instance_id"])
        eligible.append(safe)

    selected = _choose(
        eligible,
        target=frozen_target,
        min_languages=min_languages,
        min_repositories=min_repositories,
        repo_cap=repo_cap,
        seed=seed,
    )
    return {
        "schema_version": "mini-gibson-real-repo-candidates/v1",
        "runnable": False,
        "qualification_status": "pending",
        "mode": mode,
        "source": {"dataset": DATASET, "revision": DATASET_REVISION, "split": "train"},
        "selection": {
            "policy_version": SELECTION_POLICY,
            "seed": seed,
            "target": frozen_target,
            "min_languages": min_languages,
            "min_repositories": min_repositories,
            "max_tasks_per_repo": repo_cap,
        },
        "registry_sources": registry_sources,
        "counts": {
            "records_seen": total,
            "eligible": len(eligible),
            "selected": len(selected),
            "rejected_by_reason": dict(sorted(rejection_counts.items())),
        },
        "candidates": selected,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise CandidateSelectionError(f"{path}:{number}: row must be an object")
            rows.append(value)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True, help="Pinned SWE-rebench JSONL export")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--mode", choices=("pilot", "development"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    records = _load_jsonl(args.records)
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    report = select_candidates(records, registry, mode=args.mode, seed=args.seed)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
