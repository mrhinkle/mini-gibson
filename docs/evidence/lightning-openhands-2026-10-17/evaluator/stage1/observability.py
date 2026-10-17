#!/usr/bin/env python3
"""Local-first Langfuse tracing and bounded Jev judging for eval results.

The deterministic harness remains the completion authority. Remote export and
judging are explicit side effects: neither runs unless its CLI flag is present,
its SDK is installed, and the caller supplies the corresponding credentials.
Credential values are never written to artifacts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


OBSERVABILITY_SCHEMA_VERSION = 1
JEV_MODEL = "jev-1.13.0"
JEV_RUBRIC_VERSION = 1
MAX_DIFF_CHARS = 12_000
MAX_EVENT_OUTPUT_CHARS = 2_000

JEV_RUBRIC = {
    "scope_minimality": {
        "instructions": (
            "Using `task`, `deterministic_result`, and `diff`, rate whether the change is "
            "the smallest semantically appropriate fix. Do not override deterministic failures."
        ),
        "criteria": [
            "No usable fix, or the change is materially out of scope",
            "A plausible fix with unnecessary or risky unrelated changes",
            "A focused fix with only minor avoidable complexity",
            "A minimal, directly targeted fix with no semantic scope drift",
        ],
    },
    "tool_use_quality": {
        "instructions": (
            "Using `steps`, rate whether the agent inspected, edited, and verified efficiently "
            "with appropriate tools. Treat missing evidence as insufficient, not as success."
        ),
        "criteria": [
            "Tool use is absent, unsafe, or unrelated to the task",
            "Tool use makes progress but is incomplete, repetitive, or poorly ordered",
            "Tool use is appropriate with only minor inefficiency",
            "Tool use is concise, well ordered, and provides strong verification evidence",
        ],
    },
    "completion_support": {
        "instructions": (
            "Using `deterministic_result` and `steps`, rate how strongly observable evidence "
            "supports completion. A failing deterministic test cannot receive the top level."
        ),
        "criteria": [
            "Completion is unsupported or contradicted by deterministic evidence",
            "Some evidence exists, but important verification is missing or failed",
            "Completion is supported by passing checks with minor evidence gaps",
            "Completion is fully supported by passing checks, policy compliance, and a coherent trace",
        ],
    },
}


def validate_remote_options(enable_langfuse: bool, enable_jev: bool) -> None:
    """Fail before model loading when a requested remote side effect is unavailable."""
    if enable_langfuse:
        missing = [
            name
            for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
            if not os.environ.get(name)
        ]
        if missing:
            raise SystemExit(f"--langfuse requires caller-provided environment variables: {', '.join(missing)}")
        try:
            import langfuse  # noqa: F401
        except ImportError as exc:
            raise SystemExit("--langfuse requires langfuse==5.0.2") from exc
    if enable_jev:
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise SystemExit("--jev requires caller-provided TYPESAFE_API_KEY")
        try:
            import typesafe_sdk  # noqa: F401
        except ImportError as exc:
            raise SystemExit("--jev requires typesafe-sdk==0.7.5") from exc


def _bounded(value: str | None, limit: int) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    return text[: limit // 2] + "\n...[bounded for remote evaluation]...\n" + text[-limit // 2 :]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_local_record(row: dict) -> dict:
    """Create the stable local trace and bounded state eligible for remote export."""
    deterministic = {
        key: row[key]
        for key in (
            "passed",
            "verify_exit",
            "invalid_responses",
            "execution_errors",
            "changed_files",
            "allowed_changes",
            "policy_violations",
            "tests_tampered",
            "turns",
            "tool_calls",
        )
    }
    task = {
        "task_id": row["task_id"],
        "arm": row["arm"],
        "model": row["model"],
        "revision": row["revision"],
        "allowed_changes": row["allowed_changes"],
    }
    state = {
        "task": task,
        "deterministic_result": deterministic,
        "diff": _bounded(row.get("unified_diff"), MAX_DIFF_CHARS),
        "steps": [
            {
                **{key: value for key, value in event.items() if key != "output"},
                **(
                    {"output": _bounded(str(event.get("output", "")), MAX_EVENT_OUTPUT_CHARS)}
                    if "output" in event
                    else {}
                ),
            }
            for event in row.get("observability_events", [])
        ],
    }
    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "jev": {
            "model": JEV_MODEL,
            "rubric_version": JEV_RUBRIC_VERSION,
            "rubric": JEV_RUBRIC,
            "status": "NOT_REQUESTED",
            "scores": None,
        },
        "langfuse": {"status": "NOT_REQUESTED", "trace_id": None},
        "state": state,
    }


def _emit_langfuse(client: Any, record: dict) -> str:
    state = record["state"]
    deterministic = state["deterministic_result"]
    with client.start_as_current_observation(
        name="mini-gibson-eval",
        as_type="agent",
        input=state["task"],
        metadata={
            "schema_version": record["schema_version"],
            "jev_model": record["jev"]["model"],
            "jev_rubric_version": record["jev"]["rubric_version"],
        },
    ) as root:
        trace_id = root.trace_id
        for event in state["steps"]:
            event_type = event.get("type")
            as_type = "generation" if event_type == "generation" else "tool"
            kwargs = {
                "name": event.get("name", event_type or "step"),
                "as_type": as_type,
                "input": event.get("input"),
            }
            if as_type == "generation":
                kwargs["model"] = state["task"]["model"]
            with client.start_as_current_observation(**kwargs) as observation:
                observation.update(
                    output=event.get("output"),
                    metadata={
                        key: value
                        for key, value in event.items()
                        if key not in {"type", "name", "input", "output"}
                    },
                )
        root.update(output={"deterministic_result": deterministic, "diff": state["diff"]})
        root.score(
            name="deterministic_pass",
            value=1.0 if deterministic["passed"] else 0.0,
            data_type="BOOLEAN",
            comment="Authoritative local test and policy gate; Jev does not override this score.",
        )
    return trace_id


def _run_jev(client: Any, record: dict) -> tuple[dict, str]:
    from typesafe_sdk import Score

    questions = {
        name: Score(instructions=spec["instructions"], criteria=spec["criteria"])
        for name, spec in JEV_RUBRIC.items()
    }
    response = client.system_one(state=record["state"], questions=questions)
    scores = {
        name: {
            "score": answer.score,
            "confidence": getattr(answer, "confidence", None),
            "probabilities": _jsonable(getattr(answer, "probabilities", None)),
            "legend": _jsonable(getattr(answer, "legend", None)),
        }
        for name, answer in response.scores.items()
    }
    return scores, str(response.model)


def export_observability(
    rows: list[dict],
    output_dir: Path,
    *,
    enable_langfuse: bool = False,
    enable_jev: bool = False,
) -> list[Path]:
    """Persist local records, then optionally export/judge completed summaries."""
    validate_remote_options(enable_langfuse, enable_jev)
    output_dir.mkdir(parents=True, exist_ok=True)
    langfuse_client = None
    jev_client = None
    if enable_langfuse:
        from langfuse import Langfuse

        langfuse_client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            base_url=os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
            tracing_enabled=True,
            environment="mini-gibson-eval",
        )
    if enable_jev:
        from typesafe_sdk import TypeSafeClient

        jev_client = TypeSafeClient(model=JEV_MODEL)

    paths: list[Path] = []
    try:
        if jev_client is not None:
            jev_client.__enter__()
        for row in rows:
            record = build_local_record(row)
            path = output_dir / f"{row['arm']}--{row['task_id']}.observability.json"
            path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
            try:
                if langfuse_client is not None:
                    record["langfuse"] = {
                        "status": "SUBMITTED",
                        "trace_id": _emit_langfuse(langfuse_client, record),
                    }
                if jev_client is not None:
                    scores, resolved_model = _run_jev(jev_client, record)
                    record["jev"].update({"status": "SCORED", "resolved_model": resolved_model, "scores": scores})
                    if langfuse_client is not None:
                        for name, score in scores.items():
                            langfuse_client.create_score(
                                trace_id=record["langfuse"]["trace_id"],
                                name=f"jev_{name}",
                                value=float(score["score"]),
                                data_type="NUMERIC",
                                metadata={
                                    "model": resolved_model,
                                    "confidence": score["confidence"],
                                    "probabilities": score["probabilities"],
                                    "legend": score["legend"],
                                    "rubric_version": JEV_RUBRIC_VERSION,
                                },
                            )
            except Exception as exc:
                record["remote_error"] = type(exc).__name__
                if langfuse_client is not None and record["langfuse"]["status"] == "NOT_REQUESTED":
                    record["langfuse"]["status"] = "ERROR"
                if jev_client is not None and record["jev"]["status"] == "NOT_REQUESTED":
                    record["jev"]["status"] = "ERROR"
                raise
            finally:
                path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
                paths.append(path)
    finally:
        if jev_client is not None:
            jev_client.__exit__(None, None, None)
        if langfuse_client is not None:
            langfuse_client.shutdown()
    return paths
