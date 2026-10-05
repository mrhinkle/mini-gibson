#!/usr/bin/env python3
"""Portable #433 Nemotron observational runner (Hermes path).

Env:
  OPENROUTER_API_KEY   required (never read from a file in-repo)
  OBS_ROOT             default: <repo>/training/dataset/observational
  HERMES_BIN           default: hermes (on PATH)
  HERMES_HOME          optional; Hermes profile home for cost/session DB
  OBS_MODEL            default: nvidia/nemotron-3.5-lightning
  OBS_PROVIDER_PIN     default: CoreWeave
  OBS_SPEND_CAP_USD    default: 47
  OBS_TARGET_ROWS      default: 300
  OBS_MAX_TURNS        default: 22
  OBS_RUN_BUDGET_S     default: 300
  OBS_WORKERS          default: 1 (use observational_runner_parallel.py for >1)
  OBS_SPEND_BASELINE_USD  optional float; if unset, spend is tracked as delta
                          from the first key lookup in this process
  OBS_RUNTIME_VERSION  default: unknown-runtime

Stop conditions:
  - OBS_ROOT/STOP file exists
  - spend >= OBS_SPEND_CAP_USD
  - rows >= OBS_TARGET_ROWS
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OBS_ROOT_DEFAULT = Path(__file__).resolve().parents[1]  # .../training/dataset/observational
REPO_ROOT = OBS_ROOT_DEFAULT.parents[2]
DEFAULT_OBS = OBS_ROOT_DEFAULT


def env_path(name: str, default: Path) -> Path:
    v = os.environ.get(name)
    return Path(v).expanduser().resolve() if v else default


OBS_ROOT = env_path("OBS_ROOT", DEFAULT_OBS)
MANIFEST = OBS_ROOT / "tasks.manifest.json"
RUNS = OBS_ROOT / "runs.jsonl"
SCHEMA = OBS_ROOT / "schema.observational.v0.1.json"
FIXTURES = OBS_ROOT / "fixtures"
TEMPLATES = OBS_ROOT / "fixture_templates"
OUTDIR = OBS_ROOT / "runs" / "scale"
STOP_FILE = OBS_ROOT / "STOP"
STATE = OUTDIR / "runner_state.json"

HERMES = Path(os.environ.get("HERMES_BIN", "hermes"))
HERMES_HOME = Path(os.environ["HERMES_HOME"]).expanduser() if os.environ.get("HERMES_HOME") else None
MODEL = os.environ.get("OBS_MODEL", "nvidia/nemotron-3.5-lightning")
PROVIDER_PIN = os.environ.get("OBS_PROVIDER_PIN", "CoreWeave")
SPEND_CAP = float(os.environ.get("OBS_SPEND_CAP_USD", "47"))
TARGET_ROWS = int(os.environ.get("OBS_TARGET_ROWS", "300"))
MAX_TURNS = int(os.environ.get("OBS_MAX_TURNS", "22"))
RUN_BUDGET = int(os.environ.get("OBS_RUN_BUDGET_S", "300"))
RUNTIME = os.environ.get(
    "OBS_RUNTIME_VERSION",
    "unknown-runtime (set OBS_RUNTIME_VERSION)",
)
SYSTEM = (
    f"DEV_OBSERVATIONAL Mini Gibson #433 baseline. Model {MODEL} "
    f"via OpenRouter pinned to {PROVIDER_PIN}. Capture observable engineering "
    "actions only. Synthetic local fixture."
)

_SPEND_BASE: float | None = None


def load_schema_required() -> list[str]:
    return json.loads(SCHEMA.read_text())["required"]


REQUIRED = load_schema_required() if SCHEMA.exists() else []


def require_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "OPENROUTER_API_KEY missing from environment. "
            "Export it; do not commit keys or /tmp env files."
        )
    if key.startswith("sk-or-") is False and len(key) < 8:
        raise SystemExit("OPENROUTER_API_KEY looks empty/invalid")
    return key


def openrouter_key_info() -> dict:
    key = require_api_key()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]


def spend_so_far() -> tuple[float, float]:
    """Return (spent_this_batch_usd, limit_remaining_usd)."""
    global _SPEND_BASE
    data = openrouter_key_info()
    remaining = float(data.get("limit_remaining") or 0)
    baseline_env = os.environ.get("OBS_SPEND_BASELINE_USD")
    if baseline_env is not None:
        base_remaining = float(baseline_env)
    else:
        if _SPEND_BASE is None:
            _SPEND_BASE = remaining
        base_remaining = _SPEND_BASE
    spent = max(0.0, base_remaining - remaining)
    return spent, remaining


def existing_rows() -> list[dict]:
    if not RUNS.exists():
        return []
    return [json.loads(l) for l in RUNS.read_text().splitlines() if l.strip()]


def existing_run_ids(rows: list[dict]) -> set[str]:
    return {r["run_id"] for r in rows}


def append_row(row: dict) -> None:
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        raise ValueError(f"schema missing {missing}")
    s = json.dumps(row, ensure_ascii=False)
    json.loads(s)
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    with RUNS.open("a") as f:
        f.write(s + "\n")


def parse_stream(path: Path) -> dict:
    tools: list[dict] = []
    files_inspected: list[str] = []
    files_edited: list[str] = []
    tests: list[str] = []
    tool_errors: list[dict] = []
    test_failures: list[dict] = []
    result = None
    session_id = None
    order = 0
    declared: set[str] = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            session_id = ev.get("session_id")
        elif t == "tool_use":
            order += 1
            name = ev.get("name")
            inp = ev.get("input") or {}
            declared.add(name)
            tools.append({"order": order, "tool": name, "arguments": inp})
            if name in ("read_file", "search_files", "list_dir", "find", "glob"):
                p = inp.get("path") or inp.get("file")
                if p and str(p) not in files_inspected:
                    files_inspected.append(str(p))
            if name in (
                "write_file",
                "patch",
                "edit_file",
                "search_replace",
                "apply_patch",
                "write_files",
            ):
                p = inp.get("path") or inp.get("file")
                if p and str(p) not in files_edited:
                    files_edited.append(str(p))
            if name in ("terminal", "run_terminal_cmd", "bash", "shell"):
                cmd = str(inp.get("command") or inp.get("cmd") or "")
                if any(x in cmd for x in ("unittest", "pytest", "test_", "node ")):
                    tests.append(cmd)
        elif t == "tool_result":
            if ev.get("is_error"):
                tool_errors.append(
                    {"tool": ev.get("name"), "output": str(ev.get("output"))[:800]}
                )
            out = str(ev.get("output") or "")
            if "FAILED" in out or "AssertionError" in out or out.startswith("Error:"):
                test_failures.append({"tool": ev.get("name"), "summary": out[:400]})
        elif t == "result":
            result = ev
            session_id = session_id or ev.get("session_id")
    return {
        "session_id": session_id,
        "tools": tools,
        "files_inspected": files_inspected,
        "files_edited": files_edited,
        "tests": tests,
        "tool_errors": tool_errors,
        "test_failures": test_failures,
        "result": result,
        "declared_tools": sorted(declared),
    }


def cost_from_db(session_id: str):
    if not session_id or not HERMES_HOME:
        return None, None
    db = HERMES_HOME / "state.db"
    if not db.exists():
        return None, None
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    row = cur.execute(
        "SELECT estimated_cost_usd, input_tokens, output_tokens, api_call_count "
        "FROM session_model_usage WHERE session_id=? AND (task='' OR task IS NULL) "
        "AND model LIKE '%nemotron%' ORDER BY last_seen DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    sess = cur.execute(
        "SELECT started_at, cwd FROM sessions WHERE id=?", (session_id,)
    ).fetchone()
    con.close()
    return row, sess


def upstream_providers(session_id: str) -> list[str]:
    if not session_id or not HERMES_HOME:
        return []
    agent_log = HERMES_HOME / "logs" / "agent.log"
    if not agent_log.exists():
        return []
    data = agent_log.read_bytes()
    if len(data) > 2_000_000:
        data = data[-2_000_000:]
    text = data.decode("utf-8", errors="ignore")
    return re.findall(rf"\[{re.escape(session_id)}\].*upstream=(\S+)", text)


def reset_fixture(task_path: Path, template_path: Path) -> None:
    if task_path.exists():
        shutil.rmtree(task_path)
    shutil.copytree(template_path, task_path)


def build_query(task: dict, fixture_abs: Path, attempt: int) -> str:
    kind = task["kind"]
    verify = task.get("verify_cmd") or "python3 -m unittest -q"
    base = f"""You are collecting a DEV_OBSERVATIONAL engineering baseline trace for Mini Gibson issue #433.
Task ID: {task['task_id']}
Attempt: {attempt}
IMPORTANT: Work ONLY inside this absolute directory: {fixture_abs}
Do not search home directories or other projects. Do not use find across /.
Read {fixture_abs}/README.md first.
"""
    if kind == "investigate":
        return (
            base
            + f"""Goal: {task.get('goal', 'investigate as described in README')}. Do not edit files.
Follow the README report format exactly, ending with VERIFIED or FAILED.
"""
        )
    return (
        base
        + f"""Goal: {task.get('goal', 'make the tests/verification pass with minimal correct changes')}.
Run verification: {verify}
When done, state clearly VERIFIED or FAILED and briefly summarize diagnosis/repair if any.
"""
    )


def independent_verify(task: dict, fixture_abs: Path) -> tuple[bool, str]:
    cmd = task.get("verify_cmd") or "true"
    if cmd == "true":
        return True, "investigate_skip_auto"
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            cwd=str(fixture_abs),
            capture_output=True,
            text=True,
            timeout=60,
        )
        ok = r.returncode == 0
        return ok, (r.stdout + r.stderr)[-500:]
    except Exception as e:
        return False, str(e)


def classify(task: dict, parsed: dict, claim: str, verify_ok: bool):
    labels: list[str] = []
    terminal = "failed"
    if task["kind"] == "investigate":
        if re.search(r"\bVERIFIED\b", claim or ""):
            terminal = "verified"
        else:
            terminal = "failed"
            labels.append("premature_completion")
    else:
        if verify_ok:
            terminal = "verified"
            labels = []
        else:
            terminal = "failed"
            if not parsed["files_edited"] and task["kind"] in (
                "fix",
                "debug",
                "refactor",
                "multifile",
                "hard",
            ):
                labels.append("insufficient_investigation")
            if parsed["test_failures"]:
                labels.append("unsuccessful_repair")
            if re.search(r"\bVERIFIED\b", claim or "") and not verify_ok:
                labels.append("premature_completion")
    fixture_str = str(FIXTURES / task["task_id"])
    for p in parsed["files_inspected"]:
        if fixture_str not in p and "observational" not in p and (
            p.startswith("/Users") or p.startswith("/home")
        ):
            if "insufficient_investigation" not in labels:
                labels.append("insufficient_investigation")
            break
    return terminal, labels


def make_row(task: dict, attempt: int, parsed: dict, verify_ok: bool, verify_out: str):
    sid = parsed["session_id"]
    result = parsed["result"] or {}
    tokens = result.get("tokens") or {}
    claim = result.get("text") or ""
    row_db, sess = cost_from_db(sid)
    ups = upstream_providers(sid)
    uniq = sorted(set(ups))
    if len(uniq) == 1:
        provider = uniq[0]
    elif uniq:
        provider = "MIXED:" + ",".join(uniq)
    else:
        provider = PROVIDER_PIN
    if sess and sess[0]:
        ts = datetime.fromtimestamp(sess[0], tz=timezone.utc).isoformat()
    else:
        ts = datetime.now(timezone.utc).isoformat()
    terminal, labels = classify(task, parsed, claim, verify_ok)
    repair_attempts = sum(
        1
        for t in parsed["tools"]
        if t["tool"]
        in (
            "patch",
            "edit_file",
            "search_replace",
            "write_file",
            "apply_patch",
            "write_files",
        )
    )
    final_patch = None
    if parsed["files_edited"]:
        parts = []
        for fp in parsed["files_edited"]:
            p = Path(fp)
            if p.exists() and "fixtures" in str(p):
                try:
                    parts.append(f"--- {fp}\n{p.read_text()[:4000]}")
                except Exception:
                    pass
        final_patch = "\n\n".join(parts) if parts else None
    diagnosis = None
    if task["kind"] in ("debug", "fix") and (
        "Diagnosis" in claim or "diagnos" in claim.lower()
    ):
        diagnosis = claim[:2000]
    cost = row_db[0] if row_db else None
    verifier = "independent_verify_pass" if verify_ok else "independent_verify_fail"
    if task["kind"] == "investigate":
        verifier = "claim_based_investigate"
    row = {
        "run_id": sid or f"missing-{task['task_id']}-{attempt}-{time.time_ns()}",
        "task_id": task["task_id"],
        "task_source": f"observational/{task['path']}",
        "timestamp": ts,
        "model": MODEL,
        "provider": provider,
        "provider_metadata": {
            "openrouter_billing_provider": "openrouter",
            "upstream_providers_observed": ups,
            "upstream_unique": uniq,
            "pin": {"only": [PROVIDER_PIN], "require_parameters": True},
            "api_call_count": row_db[3] if row_db else None,
            "attempt": attempt,
        },
        "split": "DEV_OBSERVATIONAL",
        "system_instructions": SYSTEM,
        "agent_runtime_version": RUNTIME,
        "declared_tools": parsed["declared_tools"],
        "tool_calls": [
            {"order": t["order"], "tool": t["tool"], "arguments": t["arguments"]}
            for t in parsed["tools"]
        ],
        "files_inspected": parsed["files_inspected"],
        "files_edited": parsed["files_edited"],
        "tests_invoked": parsed["tests"],
        "tool_errors": parsed["tool_errors"],
        "test_failures": parsed["test_failures"],
        "diagnosis_after_failure": diagnosis,
        "repair_attempts": repair_attempts,
        "retry_count": max(0, repair_attempts - 1) if repair_attempts else 0,
        "final_patch": final_patch,
        "completion_claim": claim,
        "verifier_outcome": verifier,
        "terminal_outcome": terminal,
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "elapsed_ms": result.get("duration_ms") or 0,
        "cost_usd": cost,
        "notes": (
            f"synthetic=true; kind={task['kind']}; lang={task.get('lang')}; "
            f"attempt={attempt}; verify_ok={verify_ok}; verify_out={verify_out[:200]!r}"
        ),
    }
    if labels:
        row["failure_labels"] = labels
    return row


def ensure_templates(manifest_tasks: list[dict]) -> Path:
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    for t in manifest_tasks:
        src = OBS_ROOT / t["path"]
        dst = TEMPLATES / t["task_id"]
        if not dst.exists() and src.exists():
            shutil.copytree(src, dst)
    return TEMPLATES


def should_stop() -> str | None:
    if STOP_FILE.exists():
        return f"STOP file present at {STOP_FILE}"
    rows = existing_rows()
    if len(rows) >= TARGET_ROWS:
        return f"target rows reached ({len(rows)}>={TARGET_ROWS})"
    try:
        spent, _ = spend_so_far()
    except Exception as e:
        return None  # don't stop solely on spend probe failure mid-run
    if spent >= SPEND_CAP * 0.98:
        return f"spend cap approaching/hit ${spent:.4f} / ${SPEND_CAP:.2f}"
    return None


def run_one(task: dict, attempt: int, tmpl_root: Path, seen_ids: set[str]):
    reason = should_stop()
    if reason:
        print(f"STOP: {reason}", flush=True)
        return None
    fixture = OBS_ROOT / task["path"]
    tmpl = tmpl_root / task["task_id"]
    if not tmpl.exists():
        raise FileNotFoundError(f"missing template {tmpl}")
    reset_fixture(fixture, tmpl)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    stream = OUTDIR / f"{task['task_id']}__a{attempt}.jsonl"
    log = OUTDIR / f"{task['task_id']}__a{attempt}.log"
    query = build_query(task, fixture.resolve(), attempt)
    env = os.environ.copy()
    if HERMES_HOME:
        env["HERMES_HOME"] = str(HERMES_HOME)
    env["OPENROUTER_API_KEY"] = require_api_key()
    cmd = [
        str(HERMES),
        "chat",
        "--oneshot",
        "-Q",
        "--format",
        "stream-json",
        "-m",
        MODEL,
        "--provider",
        "openrouter",
        "--in",
        str(fixture),
        "--max-turns",
        str(MAX_TURNS),
        "--run-budget",
        str(RUN_BUDGET),
        "--ignore-rules",
        "-q",
        query,
    ]
    t0 = time.time()
    with stream.open("w") as so, log.open("w") as lo:
        proc = subprocess.run(
            cmd, stdout=so, stderr=lo, env=env, timeout=RUN_BUDGET + 120
        )
    elapsed = time.time() - t0
    if not stream.exists() or stream.stat().st_size == 0:
        print(f"  empty stream exit={proc.returncode}", flush=True)
        return None
    parsed = parse_stream(stream)
    sid = parsed.get("session_id")
    if not sid:
        print("  no session_id", flush=True)
        return None
    if sid in seen_ids:
        print(f"  dedupe skip {sid}", flush=True)
        return None
    verify_ok, verify_out = independent_verify(task, fixture)
    row = make_row(task, attempt, parsed, verify_ok, verify_out)
    append_row(row)
    seen_ids.add(row["run_id"])
    print(
        f"  ok {row['run_id']} outcome={row['terminal_outcome']} "
        f"provider={row['provider']} tools={len(row['tool_calls'])} "
        f"${row.get('cost_usd')} wall={elapsed:.1f}s",
        flush=True,
    )
    return row


def main() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"missing manifest {MANIFEST}")
    if shutil.which(str(HERMES)) is None and not Path(HERMES).exists():
        raise SystemExit(
            f"HERMES_BIN not found: {HERMES}. Install Hermes or use the "
            "Codex/Claude computer-use prompts in docs/433-agent-kit/PROMPTS/ "
            "(no Hermes required)."
        )
    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    tasks = manifest["tasks"]
    tmpl_root = ensure_templates(tasks)
    rows = existing_rows()
    seen = existing_run_ids(rows)
    print(
        f"start rows={len(rows)} tasks={len(tasks)} target={TARGET_ROWS} "
        f"spend_cap=${SPEND_CAP} model={MODEL} pin={PROVIDER_PIN} "
        f"obs_root={OBS_ROOT}",
        flush=True,
    )
    try:
        spent, rem = spend_so_far()
        print(f"spend_so_far=${spent:.4f} remaining=${rem:.4f}", flush=True)
    except Exception as e:
        print(f"spend probe failed (continuing): {e}", flush=True)

    attempt = 1
    while len(existing_rows()) < TARGET_ROWS and attempt <= 8:
        reason = should_stop()
        if reason:
            print(f"STOP: {reason}", flush=True)
            break
        print(
            f"=== attempt round {attempt} rows={len(existing_rows())} ===",
            flush=True,
        )
        for task in tasks:
            reason = should_stop()
            if reason:
                print(f"STOP: {reason}", flush=True)
                return
            rows_now = existing_rows()
            have = sum(1 for r in rows_now if r.get("task_id") == task["task_id"])
            if have >= attempt or have >= 6:
                continue
            print(
                f"run {task['task_id']} attempt={attempt} (have={have})",
                flush=True,
            )
            try:
                run_one(task, attempt, tmpl_root, seen)
            except subprocess.TimeoutExpired:
                print("  TIMEOUT", flush=True)
            except Exception as e:
                print(f"  ERROR {type(e).__name__}: {e}", flush=True)
            time.sleep(1)
        attempt += 1
        try:
            spent_now = spend_so_far()[0]
        except Exception:
            spent_now = None
        STATE.write_text(
            json.dumps(
                {
                    "rows": len(existing_rows()),
                    "attempt_round": attempt,
                    "spent": spent_now,
                },
                indent=2,
            )
        )

    try:
        spent, rem = spend_so_far()
        print(
            f"DONE rows={len(existing_rows())} spend=${spent:.4f} remaining=${rem:.4f}",
            flush=True,
        )
    except Exception:
        print(f"DONE rows={len(existing_rows())}", flush=True)


if __name__ == "__main__":
    main()
