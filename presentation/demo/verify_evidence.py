#!/usr/bin/env python3
"""Recount the published development receipts; does not run or score a model."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
evidence = root / "evidence"
summary = json.loads((evidence / "lightning-v7-development-summary.json").read_text())
rows = [json.loads(line) for line in (evidence / "lightning-v7-development-task-receipts.jsonl").read_text().splitlines() if line]
arms = {arm: [row for row in rows if row["arm"] == arm] for arm in ("base", "openhands-lightning")}
assert len(rows) == 48
for arm, records in arms.items():
    assert len(records) == 24 and len({r["task_id"] for r in records}) == 24, arm
    assert not any(r["tests_tampered"] or r["policy_violation_count"] for r in records), arm
base = {r["task_id"]: r for r in arms["base"]}
adapter = {r["task_id"]: r for r in arms["openhands-lightning"]}
assert base.keys() == adapter.keys()
for task in base:
    assert base[task]["task_fixture_sha256"] == adapter[task]["task_fixture_sha256"]
counts = {"base_pass": sum(r["passed"] for r in base.values()), "tuned_pass": sum(r["passed"] for r in adapter.values())}
assert counts == {"base_pass": 6, "tuned_pass": 12}
for key, value in counts.items():
    assert summary["observed_outcomes"][key] == value
lock = evidence / "lightning-v7-provenance-lock.json"
assert hashlib.sha256(lock.read_bytes()).hexdigest() == summary["provenance_lock_sha256"]
rehearsal = json.loads((evidence / "ocr7b-rehearsal-summary.json").read_text())
for name, key in (("training", "training_metrics_sha256"), ("validation", "validation_metrics_sha256")):
    metric = evidence / f"ocr7b-metrics/{name}.jsonl"
    assert hashlib.sha256(metric.read_bytes()).hexdigest() == rehearsal["training"][key]
steps = [json.loads(line)["step"] for line in (evidence / "ocr7b-metrics/training.jsonl").read_text().splitlines() if line]
assert len(steps) == 20 and set(steps) == set(range(20))
print("PASS: 7B has 20 distinct optimizer-step records; 30B v7 development counts are base 6/24 and adapter 12/24.")
print("This verifies published counts and hashes, not held-out quality, training provenance, or reduced human intervention.")
