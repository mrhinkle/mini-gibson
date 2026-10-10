#!/usr/bin/env bash
# trace.sh — flight recorder for Gibson runner invocations (DRAFT for issues #1, #2, #3-guard)
#
# Source from scripts/loop.sh:   . "$GIBSON_ROOT/scripts/lib/trace.sh"
# Then replace a runner call like:
#   run_with_wall_timeout "$RUNNER_TIMEOUT" bash -c 'cd "$1" && exec claude -p --output-format text --permission-mode acceptEdits' _ "$REPO" < "$prompt_file"
# with:
#   trace_begin --repo "$REPO" --runner claude --role builder --issue "$ISSUE" --prompt-file "$prompt_file"
#   trace_run_claude "$RUNNER_TIMEOUT" "$REPO" "$prompt_file"; rc=$?
#   trace_end "$rc"
#
# Contract (epic non-negotiables):
#   - the text written to stdout is what the loop received before (final assistant text), so callers don't change
#   - capture failure never changes rc or stdout; it sets trace_status=failed
#   - GIBSON_TRACE=0 disables everything (kill switch)
#   - never writes inside a git worktree (raw traces carry secrets)
#
# Requires: jq. Flags marked VERIFY must be checked with --help on the loop host before merge.

GIBSON_TRACE="${GIBSON_TRACE:-1}"
GIBSON_TRACE_ROOT="${GIBSON_TRACE_ROOT:-$HOME/gibson-traces}"

_trace_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
_trace_warn() { printf 'trace: %s\n' "$*" >&2; }
_trace_sha256() { { command -v shasum >/dev/null && shasum -a 256 "$1" || sha256sum "$1"; } 2>/dev/null | awk '{print $1}'; }

_trace_root_ok() {
  # Refuse any root that lives inside a git worktree (AC #3.1).
  mkdir -p "$GIBSON_TRACE_ROOT" 2>/dev/null || return 1
  chmod 700 "$GIBSON_TRACE_ROOT" 2>/dev/null || true
  if git -C "$GIBSON_TRACE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    _trace_warn "refusing: $GIBSON_TRACE_ROOT is inside a git worktree"
    return 1
  fi
  command -v jq >/dev/null || { _trace_warn "jq not found"; return 1; }
}

# trace_begin --repo DIR --runner NAME --role ROLE [--issue N] [--pr N] [--lane NAME] [--model NAME] --prompt-file FILE
trace_begin() {
  TRACE_ON=0; TRACE_DIR=""; TRACE_STATUS="disabled"; TRACE_MODE="none"; TRACE_REASON=""
  [[ "$GIBSON_TRACE" == "1" ]] || return 0
  local repo="" runner="" role="" issue="" pr="" lane="" model="" prompt=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo) repo="$2"; shift 2 ;; --runner) runner="$2"; shift 2 ;; --role) role="$2"; shift 2 ;;
      --issue) issue="$2"; shift 2 ;; --pr) pr="$2"; shift 2 ;; --lane) lane="$2"; shift 2 ;;
      --model) model="$2"; shift 2 ;; --prompt-file) prompt="$2"; shift 2 ;; *) shift ;;
    esac
  done
  _trace_root_ok || { TRACE_STATUS="failed"; TRACE_REASON="root_unusable"; return 0; }
  local repo_name; repo_name="$(basename "$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || echo "$repo")")"
  TRACE_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${runner}-${role}-$$-$RANDOM"
  TRACE_DIR="$GIBSON_TRACE_ROOT/raw/$repo_name/$(date -u +%Y-%m-%d)/$TRACE_RUN_ID"
  mkdir -p "$TRACE_DIR" || { TRACE_STATUS="failed"; TRACE_REASON="mkdir"; return 0; }
  TRACE_ON=1; TRACE_STATUS="capturing"; TRACE_REPO="$repo"
  TRACE_STARTED="$(_trace_now)"
  TRACE_HEAD_START="$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo "")"
  jq -n --arg run_id "$TRACE_RUN_ID" --arg repo "$repo_name" --arg runner "$runner" --arg role "$role" \
        --arg issue "$issue" --arg pr "$pr" --arg lane "$lane" --arg model "$model" \
        --arg prompt_sha256 "$( [[ -f "$prompt" ]] && _trace_sha256 "$prompt" )" \
        --arg head "$TRACE_HEAD_START" --arg started "$TRACE_STARTED" \
    '{schema:"run-record.v1", run_id:$run_id, repo:$repo, runner:$runner, role:$role,
      issue:(if $issue=="" then null else $issue end), pr:(if $pr=="" then null else $pr end),
      lane:(if $lane=="" then null else $lane end), model:(if $model=="" then null else $model end),
      prompt_sha256:$prompt_sha256, head_sha_start:$head, started_at:$started}' \
    > "$TRACE_DIR/record.partial.json" 2>/dev/null || TRACE_STATUS="failed"
  [[ -f "$prompt" ]] && cp "$prompt" "$TRACE_DIR/prompt.md" 2>/dev/null
  return 0
}

# Extract final text from a Claude stream-json file: the `result` field of the last result event.
_trace_claude_final() { jq -r 'select(.type=="result") | .result // empty' "$1" 2>/dev/null | tail -n 1; }

# trace_run_claude TIMEOUT REPO PROMPT_FILE  → prints final text, returns runner rc
trace_run_claude() {
  local timeout="$1" repo="$2" prompt="$3" rc
  if [[ "${TRACE_ON:-0}" != "1" ]]; then
    run_with_wall_timeout "$timeout" bash -c 'cd "$1" && exec claude -p --output-format text --permission-mode acceptEdits' _ "$repo" < "$prompt"
    return $?
  fi
  TRACE_MODE="claude-stream-json"
  local events="$TRACE_DIR/events.claude.jsonl"
  # Verified 2026-10-04 on claude 2.1.289 (Mac + Mini).
  run_with_wall_timeout "$timeout" bash -c 'cd "$1" && exec claude -p --output-format stream-json --verbose --permission-mode acceptEdits' _ "$repo" < "$prompt" > "$events"
  rc=$?
  local final; final="$(_trace_claude_final "$events")"
  if [[ -z "$final" ]]; then
    TRACE_STATUS="failed"; TRACE_REASON="no_result_event"
    # Fall back to raw stream so the loop still sees *something* rather than silence.
    cat "$events"
  else
    printf '%s\n' "$final"
  fi
  return "$rc"
}

# trace_run_codex TIMEOUT REPO PROMPT_FILE [extra codex args...]
trace_run_codex() {
  local timeout="$1" repo="$2" prompt="$3"; shift 3
  local args=("$@"); [[ ${#args[@]} -eq 0 ]] && args=(--full-auto)
  if [[ "${TRACE_ON:-0}" != "1" ]]; then
    run_with_wall_timeout "$timeout" codex exec "${args[@]}" --cd "$repo" - < "$prompt"; return $?
  fi
  TRACE_MODE="codex-json"
  local events="$TRACE_DIR/events.codex.jsonl" rc
  # Verified 2026-10-04 on codex-cli 0.154.0: --json emits thread/turn/item.* events (fixture: tests/fixtures/codex.real.jsonl).
  run_with_wall_timeout "$timeout" codex exec --json "${args[@]}" --cd "$repo" - < "$prompt" > "$events"
  rc=$?
  # Final text: last agent message. Event naming varies by codex version, so try known shapes.
  local final
  final="$(jq -r '
      (select(.type=="item.completed" and .item.type=="agent_message") | .item.text)
      // (select(.msg.type=="agent_message") | .msg.message)
      // empty' "$events" 2>/dev/null | tail -n 1)"
  if [[ -z "$final" ]]; then TRACE_STATUS="failed"; TRACE_REASON="no_agent_message"; cat "$events"; else printf '%s\n' "$final"; fi
  return "$rc"
}

# trace_run_grok TIMEOUT REPO PROMPT_FILE
trace_run_grok() {
  local timeout="$1" repo="$2" prompt="$3" rc
  if [[ "${TRACE_ON:-0}" != "1" ]]; then
    run_with_wall_timeout "$timeout" grok --prompt-file "$prompt" --cwd "$repo" --permission-mode bypassPermissions; return $?
  fi
  # Verified 2026-10-04 on grok 1.0.13 (Mac + Mini): --output-format streaming-messages-json emits
  # NDJSON in the Anthropic Messages wire format (system/assistant/user/result), same as claude stream-json.
  TRACE_MODE="grok-messages-json"
  local events="$TRACE_DIR/events.grok.jsonl"
  run_with_wall_timeout "$timeout" grok --prompt-file "$prompt" --cwd "$repo" --permission-mode bypassPermissions \
    --output-format streaming-messages-json > "$events"
  rc=$?
  local final; final="$(_trace_claude_final "$events")"
  if [[ -z "$final" ]]; then TRACE_STATUS="failed"; TRACE_REASON="no_result_event"; cat "$events"; else printf '%s\n' "$final"; fi
  return "$rc"
}

# trace_end RC [--gate-exit N] [--gate-log FILE] [--claimed success|partial|blocked|none]
trace_end() {
  [[ "${TRACE_ON:-0}" == "1" ]] || return 0
  local rc="$1"; shift; local gate_exit="" gate_log="" claimed=""
  while [[ $# -gt 0 ]]; do
    case "$1" in --gate-exit) gate_exit="$2"; shift 2 ;; --gate-log) gate_log="$2"; shift 2 ;; --claimed) claimed="$2"; shift 2 ;; *) shift ;; esac
  done
  [[ "$TRACE_STATUS" == "capturing" ]] && TRACE_STATUS="ok"
  local head_end; head_end="$(git -C "$TRACE_REPO" rev-parse HEAD 2>/dev/null || echo "")"
  [[ -n "$gate_log" && -f "$gate_log" ]] && cp "$gate_log" "$TRACE_DIR/gate.log" 2>/dev/null
  [[ -n "$TRACE_HEAD_START" && -n "$head_end" && "$TRACE_HEAD_START" != "$head_end" ]] && \
    git -C "$TRACE_REPO" diff "$TRACE_HEAD_START" "$head_end" > "$TRACE_DIR/diff.patch" 2>/dev/null
  local premature="null"
  [[ "$claimed" == "success" && -n "$gate_exit" ]] && { [[ "$gate_exit" != "0" ]] && premature="true" || premature="false"; }
  jq --arg ended "$(_trace_now)" --arg head "$head_end" --argjson rc "$rc" \
     --arg mode "$TRACE_MODE" --arg status "$TRACE_STATUS" --arg reason "$TRACE_REASON" \
     --arg gate "$gate_exit" --arg claimed "$claimed" --argjson premature "$premature" \
    '. + {ended_at:$ended, head_sha_end:$head, exit_code:$rc, timed_out:($rc==124),
          trace_mode:$mode, trace_status:$status, trace_reason:(if $reason=="" then null else $reason end),
          labels:{harness:{gate_exit:(if $gate=="" then null else ($gate|tonumber) end),
                           claimed_status:(if $claimed=="" then null else $claimed end),
                           premature_completion:$premature}}}' \
    "$TRACE_DIR/record.partial.json" > "$TRACE_DIR/record.json" 2>/dev/null \
    && rm -f "$TRACE_DIR/record.partial.json"
  # Scrub immediately so a clean copy exists even if the host dies later (issue #3).
  local scrub; scrub="$(dirname "${BASH_SOURCE[0]}")/../trace-scrub.sh"
  [[ -x "$scrub" ]] && "$scrub" "$TRACE_DIR" >/dev/null 2>&1 &
  return 0
}
