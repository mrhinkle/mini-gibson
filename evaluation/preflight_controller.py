"""Durable one-image-at-a-time controller for the compatibility preflight.

The controller is intentionally outcome-blind. It pulls the next immutable
image, runs one base/gold patch-mechanics preflight, removes that exact image,
and fsyncs public-safe progress. Docker registry output is bounded and never
written to the progress log. Rate-limit retries are bounded and resumable.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import selectors
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .cohort import dump_canonical_json
from .docker_backend import DockerBackend
from .preflight_candidates import (
    PreflightJournal,
    finalize,
    preflight_invariants,
    run_pending,
)
from .qualify_candidates import (
    QualificationOrchestrationError,
    _candidate_sequence,
    load_frozen_inputs,
    verify_local_image,
)


STATUS_SCHEMA = "mini-gibson-compatibility-preflight-controller/v1"
MIN_FREE_BYTES = 32 * 1024**3
PULL_OUTPUT_LIMIT = 128 * 1024
MAX_RATE_LIMIT_RETRIES = 24


@dataclass(frozen=True)
class BoundedCommandResult:
    returncode: int
    output: bytes
    truncated: bool
    timed_out: bool


def _run_bounded(
    argv: Sequence[str],
    *,
    timeout_s: int,
    max_output_bytes: int,
    env: Mapping[str, str],
) -> BoundedCommandResult:
    process = subprocess.Popen(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(env),
        bufsize=0,
    )
    if process.stdout is None:
        process.kill()
        raise QualificationOrchestrationError("Docker command output pipe was unavailable")
    os.set_blocking(process.stdout.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    truncated = False
    timed_out = False
    deadline = time.monotonic() + timeout_s
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0 and process.poll() is None:
                timed_out = True
                process.kill()
            events = selector.select(timeout=max(0.0, min(0.25, remaining)))
            if not events and process.poll() is not None:
                continue
            for key, _mask in events:
                try:
                    block = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not block:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                room = max_output_bytes - len(output)
                output.extend(block[: max(0, room)])
                if len(block) > room:
                    truncated = True
                    process.kill()
        returncode = process.wait(timeout=5)
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    return BoundedCommandResult(returncode, bytes(output), truncated, timed_out)


def _pull_classification(result: BoundedCommandResult) -> str:
    if result.timed_out:
        return "timeout"
    if result.truncated:
        return "output_limit"
    if result.returncode == 0:
        return "success"
    folded = result.output.lower()
    rate_limit_signatures = (
        b"toomanyrequests",
        b"too many requests",
        b"status code 429",
        b"status: 429",
        b"http 429",
        b"429 rate limit",
    )
    if any(signature in folded for signature in rate_limit_signatures):
        return "rate_limited"
    return "failed"


def _docker_env() -> dict[str, str]:
    config = os.environ.get("DOCKER_CONFIG")
    if not config or not Path(config).is_dir():
        raise QualificationOrchestrationError(
            "DOCKER_CONFIG must name the existing private registry configuration directory"
        )
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "DOCKER_CONFIG": config,
    }


def _write_event(log_path: Path, event: Mapping[str, object]) -> None:
    payload = dump_canonical_json(event)
    descriptor = os.open(log_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        if os.write(descriptor, payload) != len(payload):
            raise QualificationOrchestrationError("short append to controller event log")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise QualificationOrchestrationError(f"status path cannot be a symlink: {path}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if os.write(descriptor, payload) != len(payload):
            raise QualificationOrchestrationError(f"short write for {path}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _source_commit(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": os.environ.get("PATH", "")},
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise QualificationOrchestrationError("could not bind controller to a Git source commit")
    return value


def _resume_state(status_path: Path, source_commit: str) -> tuple[int, int, str | None]:
    if not status_path.exists():
        return int(time.time()), 0, None
    if status_path.is_symlink():
        raise QualificationOrchestrationError("status path cannot be a symlink")
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationOrchestrationError("prior controller status is unreadable") from exc
    if (
        not isinstance(status, dict)
        or status.get("schema_version") != STATUS_SCHEMA
        or status.get("source_commit") != source_commit
        or not isinstance(status.get("started_unix"), int)
        or status["started_unix"] <= 0
        or not isinstance(status.get("rate_limit_retries"), int)
        or not (0 <= status["rate_limit_retries"] <= MAX_RATE_LIMIT_RETRIES)
        or not isinstance(status.get("state"), str)
    ):
        raise QualificationOrchestrationError("prior controller status disagrees with this run")
    return status["started_unix"], status["rate_limit_retries"], status["state"]


def _status(
    *,
    source_commit: str,
    recorded: int,
    compatible: int,
    remaining: int,
    journal_head_sha256: str,
    state: str,
    current_instance_id: str | None,
    rate_limit_retries: int,
    started_unix: int,
    hourly_rate_usd: float,
) -> dict[str, object]:
    elapsed_hours = max(0.0, (time.time() - started_unix) / 3600)
    return {
        "schema_version": STATUS_SCHEMA,
        "source_commit": source_commit,
        "state": state,
        "recorded": recorded,
        "compatible": compatible,
        "incompatible": recorded - compatible,
        "remaining": remaining,
        "current_instance_id": current_instance_id,
        "journal_head_sha256": journal_head_sha256,
        "rate_limit_retries": rate_limit_retries,
        "started_unix": started_unix,
        "updated_unix": int(time.time()),
        "hourly_rate_usd": hourly_rate_usd,
        "estimated_controller_window_cost_usd": round(elapsed_hours * hourly_rate_usd, 4),
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    freeze = Path("evaluation/frozen/mini-gibson-v2-sequential-2026-10-17")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, default=freeze / "sequential-plan.json")
    parser.add_argument("--registry", type=Path, default=freeze / "pre-plan-exclusions.json")
    parser.add_argument("--freeze-evidence", type=Path, default=freeze / "freeze-evidence.json")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--material-package", type=Path, required=True)
    parser.add_argument("--image-lock", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--hourly-rate-usd", type=float, required=True)
    parser.add_argument("--rate-limit-wait-seconds", type=int, default=900)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not (0 < args.hourly_rate_usd < 30):
        raise SystemExit("--hourly-rate-usd must be positive and below the approved $30/hour cap")
    if not (60 <= args.rate_limit_wait_seconds <= 3600):
        raise SystemExit("--rate-limit-wait-seconds must be between 60 and 3600")
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise QualificationOrchestrationError("output root cannot be a symlink")
    lock_path = root / "controller.lock"
    lock_handle: BinaryIO = lock_path.open("a+b")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise QualificationOrchestrationError("another preflight controller holds the lock") from exc

    repo_root = args.repo_root.resolve()
    source_commit = _source_commit(repo_root)
    docker_env = _docker_env()
    inputs = load_frozen_inputs(
        repo_root=repo_root,
        plan_path=args.plan,
        registry_path=args.registry,
        evidence_path=args.freeze_evidence,
        dataset_path=args.dataset,
        material_package_path=args.material_package,
        image_lock_path=args.image_lock,
    )
    invariants = preflight_invariants(inputs)
    ordered = _candidate_sequence(inputs.plan)
    expected_ids = [candidate["instance_id"] for _, candidate in ordered]
    journal_path = root / "compatibility-preflight.jsonl"
    manifest_path = root / "compatibility-manifest.json"
    status_path = root / "STATUS.json"
    log_path = root / "events.jsonl"
    started_unix, retries, prior_state = _resume_state(status_path, source_commit)
    if prior_state == "terminal_controller_failure":
        raise QualificationOrchestrationError(
            "prior controller state is terminal and requires diagnosis before a new run"
        )
    if prior_state in {
        "preflight_complete_compatible",
        "preflight_complete_incompatible",
    }:
        return 0
    backend = DockerBackend(docker=args.docker)
    last_recorded = 0
    last_compatible = 0
    last_remaining = len(expected_ids)
    last_head = "0" * 64
    last_instance_id: str | None = None

    try:
        with PreflightJournal(journal_path, invariants, expected_ids) as journal:
            last_recorded = len(journal.records)
            last_compatible = sum(
                bool(row["receipt"]["compatible"]) for row in journal.records.values()
            )
            last_remaining = len(expected_ids) - last_recorded
            last_head = journal.last_sha256
            while len(journal.records) < len(expected_ids):
                free_bytes = shutil.disk_usage(root).free
                if free_bytes < MIN_FREE_BYTES:
                    raise QualificationOrchestrationError(
                        f"storage safety floor crossed: {free_bytes} bytes free"
                    )
                next_candidate = next(
                    candidate
                    for _cohort, candidate in ordered
                    if candidate["instance_id"] not in journal.records
                )
                instance_id = next_candidate["instance_id"]
                last_instance_id = instance_id
                reference = inputs.images[instance_id]["reference"]
                current = _status(
                    source_commit=source_commit,
                    recorded=len(journal.records),
                    compatible=sum(
                        bool(row["receipt"]["compatible"])
                        for row in journal.records.values()
                    ),
                    remaining=len(expected_ids) - len(journal.records),
                    journal_head_sha256=journal.last_sha256,
                    state="pulling",
                    current_instance_id=instance_id,
                    rate_limit_retries=retries,
                    started_unix=started_unix,
                    hourly_rate_usd=args.hourly_rate_usd,
                )
                _replace_atomic(status_path, dump_canonical_json(current))
                pulled = _run_bounded(
                    [args.docker, "pull", "--platform", "linux/amd64", reference],
                    timeout_s=1800,
                    max_output_bytes=PULL_OUTPUT_LIMIT,
                    env=docker_env,
                )
                classification = _pull_classification(pulled)
                if classification == "rate_limited":
                    retries += 1
                    _write_event(
                        log_path,
                        {
                            "event": "registry_rate_limited",
                            "instance_id": instance_id,
                            "retry": retries,
                            "timestamp_unix": int(time.time()),
                        },
                    )
                    if retries >= MAX_RATE_LIMIT_RETRIES:
                        raise QualificationOrchestrationError(
                            "registry rate limit made no progress for 24 retries"
                        )
                    current = _status(
                        source_commit=source_commit,
                        recorded=len(journal.records),
                        compatible=sum(
                            bool(row["receipt"]["compatible"])
                            for row in journal.records.values()
                        ),
                        remaining=len(expected_ids) - len(journal.records),
                        journal_head_sha256=journal.last_sha256,
                        state="registry_rate_limited",
                        current_instance_id=instance_id,
                        rate_limit_retries=retries,
                        started_unix=started_unix,
                        hourly_rate_usd=args.hourly_rate_usd,
                    )
                    _replace_atomic(status_path, dump_canonical_json(current))
                    time.sleep(args.rate_limit_wait_seconds)
                    continue
                if classification != "success":
                    raise QualificationOrchestrationError(
                        f"immutable image pull failed safely ({classification}) for {instance_id}"
                    )
                retries = 0
                try:
                    status = run_pending(
                        inputs,
                        journal,
                        backend=backend,
                        image_verifier=lambda image: verify_local_image(
                            image, docker=args.docker
                        ),
                        invariants=invariants,
                        limit=1,
                    )
                finally:
                    _run_bounded(
                        [args.docker, "image", "rm", reference],
                        timeout_s=120,
                        max_output_bytes=PULL_OUTPUT_LIMIT,
                        env=docker_env,
                    )
                _write_event(
                    log_path,
                    {
                        "event": "compatibility_receipt_recorded",
                        "instance_id": instance_id,
                        "compatible": bool(
                            journal.records[instance_id]["receipt"]["compatible"]
                        ),
                        "recorded": status["recorded"],
                        "journal_head_sha256": status["journal_head_sha256"],
                        "timestamp_unix": int(time.time()),
                    },
                )
                current = _status(
                    source_commit=source_commit,
                    recorded=status["recorded"],
                    compatible=status["compatible"],
                    remaining=status["remaining"],
                    journal_head_sha256=status["journal_head_sha256"],
                    state="preflighting" if status["remaining"] else "finalizing",
                    current_instance_id=None,
                    rate_limit_retries=retries,
                    started_unix=started_unix,
                    hourly_rate_usd=args.hourly_rate_usd,
                )
                _replace_atomic(status_path, dump_canonical_json(current))
                last_recorded = status["recorded"]
                last_compatible = status["compatible"]
                last_remaining = status["remaining"]
                last_head = status["journal_head_sha256"]
                last_instance_id = None

            manifest = finalize(inputs, journal, manifest_path, invariants)
            final_state = manifest["status"]
            final_status = _status(
                source_commit=source_commit,
                recorded=len(journal.records),
                compatible=manifest["compatible_count"],
                remaining=0,
                journal_head_sha256=journal.last_sha256,
                state=final_state,
                current_instance_id=None,
                rate_limit_retries=retries,
                started_unix=started_unix,
                hourly_rate_usd=args.hourly_rate_usd,
            )
            final_status["manifest_sha256"] = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            _replace_atomic(status_path, dump_canonical_json(final_status))
            _write_event(
                log_path,
                {
                    "event": final_state,
                    "recorded": len(journal.records),
                    "compatible": manifest["compatible_count"],
                    "incompatible": manifest["incompatible_count"],
                    "timestamp_unix": int(time.time()),
                },
            )
    except Exception as exc:
        failure = _status(
            source_commit=source_commit,
            recorded=last_recorded,
            compatible=last_compatible,
            remaining=last_remaining,
            journal_head_sha256=last_head,
            state="terminal_controller_failure",
            current_instance_id=last_instance_id,
            rate_limit_retries=retries,
            started_unix=started_unix,
            hourly_rate_usd=args.hourly_rate_usd,
        )
        failure["error_type"] = type(exc).__name__
        _replace_atomic(status_path, dump_canonical_json(failure))
        _write_event(
            log_path,
            {
                "event": "terminal_controller_failure",
                "error_type": type(exc).__name__,
                "recorded": last_recorded,
                "timestamp_unix": int(time.time()),
            },
        )
        raise
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
