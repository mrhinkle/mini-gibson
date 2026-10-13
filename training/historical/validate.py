"""Schema check, secret re-scan, and aggregate stats for historical SFT JSONL.

Token estimate is len(text)//4. No tokenizer dependency. The estimate is what
the 4k tool cap and 32k episode cap use.

Usage: python3 training/historical/validate.py JSONL [JSONL ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from training.historical.redact import residual_json_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "training" / "dataset" / "schema.json"
EPISODE_TOKEN_LIMIT = 32768
TOOL_TOKEN_LIMIT = 4096

_PR_URL = re.compile(r"^https://github\.com/The-AIE/[A-Za-z0-9._-]+/pull/\d+$")
_SESSION_PROV = re.compile(r"^session:[0-9a-f]{16,64}$")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + 3) // 4


def message_tokens(message: dict) -> int:
    total = 4 + estimate_tokens(message.get("content") or "")
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        total += 4
        total += estimate_tokens(str(fn.get("name") or ""))
        total += estimate_tokens(str(fn.get("arguments") or ""))
    if message.get("tool_call_id"):
        total += estimate_tokens(str(message.get("tool_call_id") or ""))
    return total


def messages_tokens(messages: list[dict]) -> int:
    return sum(message_tokens(m) for m in messages)


def load_schema(path: Path | None = None) -> dict:
    return json.loads((path or SCHEMA_PATH).read_text(encoding="utf-8"))


def check_schema(record: dict, schema: dict | None = None) -> list[str]:
    """Return error codes. Does not echo record content."""
    schema = schema or load_schema()
    errors: list[str] = []
    for key in schema.get("required") or []:
        if key not in record:
            errors.append(f"missing:{key}")
    props = schema.get("properties") or {}
    if "episode_id" in record and not isinstance(record["episode_id"], str):
        errors.append("episode_id")
    elif isinstance(record.get("episode_id"), str) and not record["episode_id"]:
        errors.append("episode_id")
    if "repo" in record and not isinstance(record["repo"], str):
        errors.append("repo")
    if "task" in record and not isinstance(record["task"], str):
        errors.append("task")
    elif isinstance(record.get("task"), str) and not record["task"].strip():
        errors.append("task_empty")
    if "issue" in record and not isinstance(record["issue"], int) and record["issue"] is not None:
        errors.append("issue")
    if "pr" in record and not isinstance(record["pr"], int) and record["pr"] is not None:
        errors.append("pr")
    outcome = props.get("outcome") or {}
    allowed = outcome.get("enum") or []
    if "outcome" in record and record["outcome"] not in allowed:
        errors.append("outcome")
    traj = record.get("trajectory")
    if "trajectory" in record:
        if not isinstance(traj, list):
            errors.append("trajectory")
        else:
            for step in traj:
                if not isinstance(step, dict) or not isinstance(step.get("phase"), str):
                    errors.append("trajectory_step")
                    break
                evidence = step.get("evidence")
                if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
                    errors.append("evidence")
                    break
    prov = record.get("provenance")
    if "provenance" in record:
        if not isinstance(prov, list) or len(prov) < 1 or any(not isinstance(item, str) or not item for item in prov):
            errors.append("provenance")
    return errors


def check_corpus(record: dict, max_episode_tokens: int = EPISODE_TOKEN_LIMIT) -> list[str]:
    """OpenAI chat/tool shape, safe provenance, and the episode token cap."""
    errors: list[str] = []
    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        errors.append("messages")
        messages = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            errors.append(f"message:{index}")
            continue
        role = message.get("role")
        if role not in ("system", "user", "assistant", "tool"):
            errors.append(f"role:{index}")
        if role == "tool" and not isinstance(message.get("tool_call_id"), str):
            errors.append(f"tool_call_id:{index}")
        if "content" in message and message["content"] is not None and not isinstance(message["content"], str):
            errors.append(f"content:{index}")
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict) or call.get("type") != "function":
                errors.append(f"tool_type:{index}")
                break
            fn = call.get("function") or {}
            if not isinstance(fn.get("name"), str) or not isinstance(fn.get("arguments"), str):
                errors.append(f"function:{index}")
                break
    if not isinstance(record.get("token_count"), int) or record.get("token_count", -1) < 0:
        errors.append("token_count")
    elif messages and messages_tokens(messages) > max_episode_tokens:
        errors.append("over_context")
    prov = record.get("provenance") or []
    if isinstance(prov, list):
        urls = [item for item in prov if isinstance(item, str) and _PR_URL.match(item)]
        sessions = [item for item in prov if isinstance(item, str) and _SESSION_PROV.match(item)]
        if len(urls) != 1 or len(sessions) != 1:
            errors.append("provenance_shape")
        for item in prov:
            if isinstance(item, str) and (item.startswith("/Users/") or item.startswith("/home/") or "mrhinkle" in item):
                errors.append("provenance_path")
                break
    return errors


def check_record(record: dict, schema: dict | None = None, max_episode_tokens: int = EPISODE_TOKEN_LIMIT) -> list[str]:
    return check_schema(record, schema) + check_corpus(record, max_episode_tokens)


def scan_line(line: str) -> list[str]:
    return residual_json_text(line)


def validate_jsonl(path: Path, max_episode_tokens: int = EPISODE_TOKEN_LIMIT) -> dict:
    """Stream the JSONL. Returns counts only."""
    schema = load_schema()
    records = 0
    bad_json = 0
    schema_errors: Counter[str] = Counter()
    secret_hits: Counter[str] = Counter()
    tokens = 0
    per_repo: Counter[str] = Counter()
    per_vendor: Counter[str] = Counter()
    over_context = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            hits = scan_line(line)
            for name in hits:
                secret_hits[name] += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                bad_json += 1
                continue
            records += 1
            for code in check_record(record, schema, max_episode_tokens):
                schema_errors[code] += 1
                if code == "over_context":
                    over_context += 1
            tokens += int(record.get("token_count") or 0)
            per_repo[str(record.get("repo") or "?")] += 1
            per_vendor[str(record.get("vendor") or "?")] += 1
    return {
        "records": records,
        "bad_json": bad_json,
        "schema_errors": dict(schema_errors),
        "secret_hits": dict(secret_hits),
        "secret_hit_total": sum(secret_hits.values()),
        "tokens": tokens,
        "per_repo_windows": dict(per_repo),
        "per_vendor_windows": dict(per_vendor),
        "over_context": over_context,
    }


def render_stats(stats: dict) -> str:
    """Markdown counts. No message content and no filesystem paths."""
    usable = int(stats.get("usable_episodes") or 0)
    windows = int(stats.get("windows") or 0)
    target = int(stats.get("target") or 300)
    version = stats.get("corpus_version") or "v1"
    builder_eps = int(((stats.get("per_role") or {}).get("builder") or {}).get("episodes") or 0)
    gap_base = builder_eps if version != "v1" else usable
    gap = max(0, target - gap_base)
    if version != "v1":
        header = [
            f"Output: ~/gibson-traces/sft/historical-{version}.jsonl (all roles on merged PRs, mode 600).",
            f"Train: ~/gibson-traces/sft/train-{version}.jsonl (builder only, temporal holdout removed, mode 600).",
            f"Holdout: ~/gibson-traces/sft/holdout-{version}.jsonl (builder episodes on the latest PRs, mode 600).",
            f"Negatives: ~/gibson-traces/sft/negatives-{version}.jsonl (builders on closed-unmerged PRs, mode 600).",
            f"Assessor: ~/gibson-traces/sft/assessor-{version}.jsonl (reviewers on merged PRs with a verdict, mode 600).",
            "Source: Mac and Mini sessions joined to a pull request.",
        ]
    else:
        header = [
            "Output: ~/gibson-traces/sft/historical-v1.jsonl (all roles, mode 600).",
            "Train: ~/gibson-traces/sft/train-v1.jsonl (builder only, temporal holdout removed, mode 600).",
            "Holdout: ~/gibson-traces/sft/holdout-v1.jsonl (builder episodes on the latest PRs, mode 600).",
            "Source: sessions.joined.csv rows on this Mac whose pr_state is MERGED.",
        ]
    lines = [
        "# Historical SFT corpus stats",
        "",
        f"Generated: {stats.get('generated', '')}",
        *header,
        "Token estimate: 4 characters per token. Tool outputs over 4096 tokens are truncated.",
        "Episodes over 32768 tokens are split into windows that each keep the system and user task.",
        "",
        "## Against the 300 target",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Usable episodes (sessions that produced a kept window) | {usable} |",
        f"| Builder episodes on merged PRs | {builder_eps} |",
        f"| Training windows written | {windows} |",
        f"| Target episodes | {target} |",
        f"| Stretch band | 300–500 |",
        f"| Gap to 300 episodes | {gap} |",
        "",
        "## Selection and drops",
        "",
        "| Reason | Count |",
        "| --- | ---: |",
        f"| Selected merged sessions | {stats.get('selected', 0)} |",
        f"| Missing file | {stats.get('missing_file', 0)} |",
        f"| Unreadable | {stats.get('unreadable', 0)} |",
        f"| Parse error | {stats.get('parse_error', 0)} |",
        f"| No grok chat_history | {stats.get('no_chat_history', 0)} |",
        f"| Empty trajectory | {stats.get('empty', 0)} |",
        f"| Dropped, residual secret | {stats.get('residual_secret', 0)} |",
        f"| Dropped, schema | {stats.get('schema_invalid', 0)} |",
        f"| Groups or windows over the episode cap | {stats.get('over_context', 0)} |",
        f"| PR metadata missing | {stats.get('pr_metadata_missing', 0)} |",
        f"| Issue task fetched from GitHub | {stats.get('issue_fetched', 0)} |",
        f"| Issue task from PR metadata body | {stats.get('issue_embedded', 0)} |",
        f"| Issue task fallback, old header | {stats.get('issue_fallback', 0)} |",
        "",
        "Residual pattern hits on dropped sessions and on windows rejected inside a kept session (names only):",
        "",
    ]
    patterns = stats.get("residual_patterns") or {}
    if patterns:
        lines += ["| Pattern | Hits |", "| --- | ---: |"]
        for name in sorted(patterns):
            lines.append(f"| {name} | {patterns[name]} |")
    else:
        lines.append("None.")
    lines += [
        "",
        "## Truncation and windowing, both ways",
        "",
        "| | Episodes | Windows |",
        "| --- | ---: | ---: |",
        f"| Within 32768 tokens after tool truncation | {stats.get('episodes_within_limit', 0)} | {stats.get('windows_from_within', 0)} |",
        f"| Over 32768 tokens, split | {stats.get('episodes_split', 0)} | {stats.get('windows_from_split', 0)} |",
        f"| Total kept | {usable} | {windows} |",
        "",
        "| Tool outputs | Count |",
        "| --- | ---: |",
        f"| Seen | {stats.get('tool_outputs_seen', 0)} |",
        f"| Truncated above 4096 tokens | {stats.get('tool_outputs_truncated', 0)} |",
        f"| Left whole | {stats.get('tool_outputs_kept', 0)} |",
        f"| Estimated tokens in tool outputs before truncation | {stats.get('tool_tokens_before', 0)} |",
        f"| Estimated tokens in tool outputs after truncation | {stats.get('tool_tokens_after', 0)} |",
        f"| Orphan tool results skipped while windowing | {stats.get('orphan_tools', 0)} |",
        "",
        f"Sum of window token_count estimates: {stats.get('tokens', 0)}",
        "",
        "## By repo (episodes / windows)",
        "",
        "| Repo | Episodes | Windows |",
        "| --- | ---: | ---: |",
    ]
    per_repo = stats.get("per_repo") or {}
    if not per_repo:
        lines.append("| (none) | 0 | 0 |")
    for repo in sorted(per_repo):
        cell = per_repo[repo]
        lines.append(f"| {repo} | {cell.get('episodes', 0)} | {cell.get('windows', 0)} |")
    lines += [
        "",
        "## By role (episodes / windows / tokens)",
        "",
        "| Role | Episodes | Windows | Tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    per_role = stats.get("per_role") or {}
    for role in ("builder", "reviewer", "other"):
        cell = per_role.get(role) or {}
        lines.append(
            f"| {role} | {cell.get('episodes', 0)} | {cell.get('windows', 0)} | {cell.get('tokens', 0)} |"
        )
    for role in sorted(per_role):
        if role in ("builder", "reviewer", "other"):
            continue
        cell = per_role[role]
        lines.append(
            f"| {role} | {cell.get('episodes', 0)} | {cell.get('windows', 0)} | {cell.get('tokens', 0)} |"
        )
    lines += [
        "",
        "## Splits",
        "",
        f"Sample seed: {stats.get('seed', '')}",
        f"Train token cap: {stats.get('train_token_cap', '')}",
        f"Holdout fraction of builder PRs: {stats.get('holdout_fraction', '')}",
        f"Holdout cutoff (earliest date-based mergedAt kept out): {stats.get('holdout_cutoff', '')}",
        f"Builder PRs: {stats.get('builder_prs', 0)}",
        f"Holdout PRs: {stats.get('holdout_prs', 0)}",
        f"Holdout PRs added by shared issue: {stats.get('holdout_lineage_prs', 0)}",
        f"Holdout/train PR overlap: {stats.get('overlap_prs', 0)}",
        f"Holdout/train episode overlap: {stats.get('overlap_episodes', 0)}",
        f"Holdout/train issue overlap: {stats.get('overlap_issues', 0)}",
        f"Windows dropped for a residual on the joined text: {stats.get('windows_residual_dropped', 0)}",
        "",
        "| Split | Episodes | Windows | Tokens |",
        "| --- | ---: | ---: | ---: |",
        f"| historical-{version}, all roles | {usable} | {windows} | {stats.get('tokens', 0)} |",
        f"| holdout-{version}, builder, latest PRs plus issue lineage | {stats.get('holdout_episodes', 0)} | {stats.get('holdout_windows', 0)} | {stats.get('holdout_tokens', 0)} |",
        f"| train pool, builder, not held out | {stats.get('pool_episodes', 0)} | {stats.get('pool_windows', 0)} | {stats.get('pool_tokens', 0)} |",
        f"| train-{version}, after sampling | {stats.get('train_episodes', 0)} | {stats.get('train_windows', 0)} | {stats.get('train_tokens', 0)} |",
        f"| builder pool left out by the cap | {stats.get('unsampled_episodes', 0)} | {stats.get('unsampled_windows', 0)} | {stats.get('unsampled_tokens', 0)} |",
        f"| negatives-{version}, builder, closed-unmerged | {stats.get('negative_episodes', 0)} | {stats.get('negative_windows', 0)} | {stats.get('negative_tokens', 0)} |",
        f"| assessor-{version}, reviewer with verdict | {stats.get('assessor_episodes', 0)} | {stats.get('assessor_windows', 0)} | {stats.get('assessor_tokens', 0)} |",
        "",
        "### Train by repo",
        "",
        "| Repo | Episodes | Windows | Tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    train_repo = stats.get("train_per_repo") or {}
    if not train_repo:
        lines.append("| (none) | 0 | 0 | 0 |")
    for repo in sorted(train_repo):
        cell = train_repo[repo]
        lines.append(
            f"| {repo} | {cell.get('episodes', 0)} | {cell.get('windows', 0)} | {cell.get('tokens', 0)} |"
        )
    lines += [
        "",
        "### Holdout by repo",
        "",
        "| Repo | Episodes | Windows | Tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    hold_repo = stats.get("holdout_per_repo") or {}
    if not hold_repo:
        lines.append("| (none) | 0 | 0 | 0 |")
    for repo in sorted(hold_repo):
        cell = hold_repo[repo]
        lines.append(
            f"| {repo} | {cell.get('episodes', 0)} | {cell.get('windows', 0)} | {cell.get('tokens', 0)} |"
        )
    lines += [
        "",
        "## By vendor (episodes / windows)",
        "",
        "| Vendor | Episodes | Windows |",
        "| --- | ---: | ---: |",
    ]
    per_vendor = stats.get("per_vendor") or {}
    if not per_vendor:
        lines.append("| (none) | 0 | 0 |")
    for vendor in sorted(per_vendor):
        cell = per_vendor[vendor]
        lines.append(f"| {vendor} | {cell.get('episodes', 0)} | {cell.get('windows', 0)} |")
    lines += [
        "",
        "## Secret re-scan of the output file",
        "",
        f"Hits: {stats.get('secret_hit_total', 0)}",
        "",
        "## Output validation",
        "",
        f"JSONL records: {stats.get('file_records', 0)}",
        f"Bad JSON lines: {stats.get('bad_json', 0)}",
        f"Schema error codes: {json.dumps(stats.get('schema_errors') or {}, sort_keys=True)}",
        "",
        "## Join method by role, repo, and vendor",
        "",
    ]
    cross = stats.get("join_cross") or {}
    if not cross:
        lines.append("No joined episodes.")
    else:
        lines += [
            "| Join method | Role | Repo | Vendor | Episodes | Windows | Tokens |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
        for key in sorted(cross):
            method, role, repo, vendor = (key.split("|") + ["?", "?", "?", "?"])[:4]
            cell = cross[key]
            lines.append(
                f"| {method} | {role} | {repo} | {vendor} | {cell.get('episodes', 0)} | "
                f"{cell.get('windows', 0)} | {cell.get('tokens', 0)} |"
            )
    lines += [
        "",
        "## Unjoined sessions",
        "",
    ]
    tally = stats.get("join_tally") or {}
    reasons = tally.get("reasons") or {}
    methods = tally.get("methods") or {}
    if not reasons and not methods:
        lines.append("No inventory tally.")
    else:
        lines += ["| Join method | Sessions |", "| --- | ---: |"]
        for name in sorted(methods):
            lines.append(f"| {name} | {methods[name]} |")
        lines += ["", "| Unjoined reason | Sessions |", "| --- | ---: |"]
        for name in sorted(reasons):
            lines.append(f"| {name} | {reasons[name]} |")
    lines += [
        "",
        "## Notes",
        "",
        "The user task is the issue title plus the first 1500 characters of the issue body.",
        "Bodies are fetched with gh issue view and cached under ~/gibson-traces/cache/.",
        "When the fetch fails, the user task stays the PR number, branch, and linked issue number.",
        "The session's own user messages follow that task.",
        "session_role is builder, reviewer, or other, from the tool calls the session made.",
        "A builder successfully edited or wrote a file, or ran git commit, in a session that was launched with write access.",
        "The edit counts when its tool result shows the file changed.",
        "A read-only sandbox, an `-s read-only` launch, or a reviewer prompt that says read-only is a reviewer.",
        "Keyword evidence breaks a tie when the session neither edited successfully nor committed.",
        "The train split keeps every the-gibson and chatterbuilt builder episode outside the holdout,",
        "then fills the token cap with conference-os builder episodes, seeded and round-robin by vendor.",
        "The holdout starts as the latest fraction of builder PRs by mergedAt.",
        "A builder PR that shares an issue with one of those PRs is moved into the holdout.",
        "The cutoff stays the earliest mergedAt among the date-based holdout PRs.",
        "A pull request, an episode, or an issue in the holdout is absent from the train split.",
        "Commit joins use SHAs the session created: git commit's [branch sha], or git rev-parse HEAD after that commit.",
        "A SHA printed by git log, git show, or rev-parse of another ref is ignored.",
        "That displayed SHA is ignored even when it equals a candidate pull request head or one of that pull request's commits.",
        "commit-merged-unique and issue-merged-unique mean several pull requests shared a commit or an issue",
        "and exactly one of them was merged. Any other ambiguous session stays unjoined.",
        "The first user prompt can declare a branch or a PR number. That is prompt-branch or prompt-pr.",
        "A declaration is read from that first prompt only. Later tool output is not a declaration.",
        "The header is the first non-empty line of that prompt, or a line that starts with TASK.",
        "When the header names exactly one branch, that branch wins. Otherwise one PR. Otherwise one issue in one repo.",
        "Without a branch, that line must name exactly one number. PR #370 and #371 is two numbers, so it is not a header.",
        "Numbers later in the prompt do not override the header. That join method is prompt-header.",
        "A header the catalog cannot resolve stays unjoined with reason header_unresolved.",
        "That header does not fall through to later numbers, a commit join, or an issue join.",
        "A branch the catalog misses can still use one PR or one issue written on that same header line.",
        "When a prompt or an issue matches several pull requests, each candidate is scored by edit coverage,",
        "the share of the session's successful edits that the pull request also changes.",
        "The highest coverage wins when it is at least 0.5 and at least 0.2 above the next one.",
        "Equal coverage prefers the candidate whose number appears on the header line. Otherwise the session stays ambiguous.",
        "That join method is coverage. Jaccard is not used to choose a pull request.",
        "A builder joined by a header, a prompt, or an issue must have at least 30% of its successful edits on that pull request.",
        "That ratio is the share of the session's edits the pull request also changes, not Jaccard.",
        "A merged pull request is the union of every session plus the coordinator commit, so Jaccard rejects a true subset.",
        "An empty edit set scores 0. A builder below 0.3 is unjoined with reason no_file_overlap.",
        "A builder whose pull request file list is unknown is unjoined with reason pr_files_unknown.",
        "A reviewer is not rejected when that file list is unknown.",
        "Joining a reviewer does not make that session a builder.",
        "A session that still matches a secret pattern after redaction is dropped and counted.",
        "The secret re-scan decodes each JSON line, checks each string, and checks the concatenation of message and tool strings.",
        "A backslash added by JSON encoding is not itself a secret.",
        "Provenance is the PR URL plus a hash of the session path. The raw path is not stored.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 training/historical/validate.py",
        usage="python3 training/historical/validate.py JSONL [JSONL ...]",
        description="Validate historical SFT JSONL files and print counts.",
    )
    parser.add_argument("jsonl", nargs="*", type=Path, help="JSONL files to validate")
    parser.add_argument("--jsonl", dest="jsonl_opt", type=Path, help="One JSONL file")
    parser.add_argument("--max-episode-tokens", type=int, default=EPISODE_TOKEN_LIMIT)
    args = parser.parse_args(argv)
    paths = list(args.jsonl)
    if args.jsonl_opt is not None:
        paths.append(args.jsonl_opt)
    if not paths:
        parser.print_usage(sys.stderr)
        return 2
    code = 0
    for path in paths:
        result = validate_jsonl(path, args.max_episode_tokens)
        summary = {k: result[k] for k in ("records", "bad_json", "secret_hit_total", "schema_errors", "tokens", "over_context")}
        print(f"{path} {json.dumps(summary, sort_keys=True)}")
        if result["secret_hit_total"] or result["bad_json"] or result["schema_errors"]:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
