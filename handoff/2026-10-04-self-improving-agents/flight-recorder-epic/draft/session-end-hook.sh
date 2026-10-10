#!/usr/bin/env bash
# session-end-hook.sh — Claude Code SessionEnd hook (DRAFT for issue #4)
#
# ~/.claude/settings.json:
#   { "hooks": { "SessionEnd": [ { "hooks": [ { "type": "command",
#       "command": "~/Code/the-gibson/adapters/claude-code/session-end-hook.sh" } ] } ] } }
#
# Reads the hook JSON from stdin (session_id, transcript_path, cwd, ...). Always exits 0.
root="${GIBSON_TRACE_ROOT:-$HOME/gibson-traces}"
log="$root/hook-errors.log"
{
  input="$(cat)"
  sid="$(jq -r '.session_id // empty' <<<"$input")"
  tp="$(jq -r '.transcript_path // empty' <<<"$input")"
  cwd="$(jq -r '.cwd // empty' <<<"$input")"
  [[ -n "$sid" && -f "$tp" ]] || exit 0
  # Only dev sessions under ~/Code, minus exclusions (issue #4 AC4).
  case "$cwd" in "$HOME/Code/"*) ;; *) exit 0 ;; esac
  IFS=',' read -ra ex <<<"${GIBSON_TRACE_EXCLUDE:-}"
  for g in "${ex[@]}"; do [[ -n "$g" && "$cwd" == $g ]] && exit 0; done
  if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then exit 0; fi
  repo="$(basename "$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || echo "$cwd")")"
  dir="$root/raw/$repo/$(date -u +%Y-%m-%d)/session-$sid"
  mkdir -p "$dir" && chmod 700 "$root"
  cp "$tp" "$dir/events.claude-session.jsonl"
  jq -n --arg sid "$sid" --arg repo "$repo" --arg cwd "$cwd" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{schema:"run-record.v1", run_id:("session-"+$sid), repo:$repo, runner:"claude", role:"interactive",
      cwd:$cwd, ended_at:$at, trace_mode:"claude-session-transcript", trace_status:"ok"}' > "$dir/record.json"
  scrub="$(dirname "$0")/../../scripts/trace-scrub.sh"
  [[ -x "$scrub" ]] && "$scrub" "$dir"
} >>"$log" 2>&1
exit 0
