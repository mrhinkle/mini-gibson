#!/usr/bin/env python3
"""Verify the frozen Lightning/OpenHands evidence with the Python standard library."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IGNORED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
}

EXPECTED_FILE_HASHES = {
    "results/stage1-base.jsonl": "1146766d2451f7baeb7d696f1fcd3197d7c8d4dad756e9b4545cdf52b959ceb6",
    "results/stage1-tuned.jsonl": "a9aee19732a0aa8c7d32f61d2b0b7ef1b6c8b5fd23c40e0410ef60499bd7843e",
    "results/stage2-base.jsonl": "76b4903d7db3e6e4186aa6cb43f330832172ed1f98b85b9580ed1c6087d1f60d",
    "results/stage2-tuned.jsonl": "0e4c00585fce317dc89a9f510dd88dcf5f8dfba11bf53d88e25a36968340e08a",
    "evaluator/stage1/eval_agent_v3.py": "43e48f468b962b55566c80d4eb09a9ce2f5b135fd415a0226ac9ed928d2a369f",
    "evaluator/stage1/lock.json": "0dc5ad19637e1f6c9925c4a3002dd884baf9f1fdfb0b491f53f039151424ac68",
    "evaluator/stage2/eval_agent_v3.py": "77fe13ff512e99fc8a1e64d42b9f7fa33a3001c8c32a243b0276783abc4bf625",
    "evaluator/stage2/lock.json": "212a540bd33c35cb93463fba7c6abdd51d2e7b870967df406c56aba8b14e19a6",
    "training/finetune-lightning.yaml": "b93a8961fef50dd78d64d9448586dfe23d6c49d4627d1c7269d77fe27aad07d8",
    "training/training-data-manifest.json": "adcc36778c0d64221133fb7d06e6b204bf972ec7f665049a0b22fbc7dbcbd704",
}

EXPECTED_OUTCOMES = {
    "stage1": {"n": 24, "base_pass": 6, "tuned_pass": 12, "wins": 8, "losses": 2},
    "stage2": {"n": 24, "base_pass": 3, "tuned_pass": 4, "wins": 4, "losses": 3},
    "combined": {"n": 48, "base_pass": 9, "tuned_pass": 16, "wins": 12, "losses": 5},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def tree_hashes(root: Path, included_tasks: set[str] | None = None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if IGNORED_PARTS.intersection(rel.parts):
            continue
        if included_tasks is not None and rel.parts[0] not in included_tasks:
            continue
        hashes[str(rel)] = sha256(path)
    return hashes


def aggregate_tree_sha256(root: Path, included_tasks: set[str] | None = None) -> str:
    payload = json.dumps(
        tree_hashes(root, included_tasks), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def task_fixture_sha256(task_id: str) -> str:
    task_root = ROOT / "fixtures" / task_id
    per_task = {
        str(path.relative_to(task_root)): sha256(path)
        for path in sorted(task_root.rglob("*"))
        if path.is_file() and not IGNORED_PARTS.intersection(path.relative_to(task_root).parts)
    }
    payload = json.dumps(per_task, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def paired_stats(base: list[dict], tuned: list[dict]) -> dict:
    assert len(base) == len(tuned)
    assert [row["task_id"] for row in base] == [row["task_id"] for row in tuned]
    wins = losses = both_pass = both_fail = 0
    for base_row, tuned_row in zip(base, tuned):
        assert base_row["task_fixture_sha256"] == tuned_row["task_fixture_sha256"]
        expected_fixture = task_fixture_sha256(base_row["task_id"])
        assert base_row["task_fixture_sha256"] == expected_fixture
        for row in (base_row, tuned_row):
            assert not row.get("harness_error")
            assert not row["policy_violations"]
            assert row["tests_tampered"] is False
            assert set(row["changed_files"]) <= set(row["allowed_changes"])
            if row["passed"]:
                assert row["verify_exit"] == 0
        pair = (bool(base_row["passed"]), bool(tuned_row["passed"]))
        if pair == (False, True):
            wins += 1
        elif pair == (True, False):
            losses += 1
        elif pair == (True, True):
            both_pass += 1
        else:
            both_fail += 1
    discordant = wins + losses
    one_sided_p = sum(math.comb(discordant, k) for k in range(wins, discordant + 1)) / (2**discordant)
    return {
        "n": len(base),
        "base_pass": sum(bool(row["passed"]) for row in base),
        "tuned_pass": sum(bool(row["passed"]) for row in tuned),
        "wins": wins,
        "losses": losses,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "one_sided_exact_p": one_sided_p,
    }


def reliability(rows: list[dict]) -> dict:
    return {
        "invalid_responses": sum(row["invalid_responses"] for row in rows),
        "generations": sum(row["generations"] for row in rows),
        "tasks_affected": sum(row["invalid_responses"] > 0 for row in rows),
    }


def main() -> None:
    for relative, expected in EXPECTED_FILE_HASHES.items():
        actual = sha256(ROOT / relative)
        assert actual == expected, f"hash mismatch for {relative}: {actual}"

    stage1_base = read_jsonl(ROOT / "results/stage1-base.jsonl")
    stage1_tuned = read_jsonl(ROOT / "results/stage1-tuned.jsonl")
    stage2_base = read_jsonl(ROOT / "results/stage2-base.jsonl")
    stage2_tuned = read_jsonl(ROOT / "results/stage2-tuned.jsonl")

    stage1_ids = {row["task_id"] for row in stage1_base}
    stage2_ids = {row["task_id"] for row in stage2_base}
    assert stage1_ids.isdisjoint(stage2_ids)
    assert aggregate_tree_sha256(ROOT / "fixtures", stage1_ids) == "6ab467372b242132e76408d3be06624ba209afc601499f4244268766014ddc81"
    assert aggregate_tree_sha256(ROOT / "fixtures") == "6fa7d526643f67becaa623be09c7bf485e6e56aaed1704d2746cdfa16f5ac0bc"

    stage1 = paired_stats(stage1_base, stage1_tuned)
    stage2 = paired_stats(stage2_base, stage2_tuned)
    combined = paired_stats(stage1_base + stage2_base, stage1_tuned + stage2_tuned)
    for name, actual in (("stage1", stage1), ("stage2", stage2), ("combined", combined)):
        for key, expected in EXPECTED_OUTCOMES[name].items():
            assert actual[key] == expected, f"{name} {key}: {actual[key]} != {expected}"

    base_reliability = reliability(stage1_base + stage2_base)
    tuned_reliability = reliability(stage1_tuned + stage2_tuned)
    assert base_reliability == {"invalid_responses": 8, "generations": 443, "tasks_affected": 8}
    assert tuned_reliability == {"invalid_responses": 21, "generations": 250, "tasks_affected": 21}

    output = {
        "verified": True,
        "outcomes": {"stage1": stage1, "stage2": stage2, "combined": combined},
        "reliability": {"base": base_reliability, "tuned": tuned_reliability},
        "training_data_manifest_sha256": sha256(ROOT / "training/training-data-manifest.json"),
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
