#!/usr/bin/env bash
# trace-scrub.sh RAW_RUN_DIR — produce clean/<...>/<run_id>/ or quarantine/<...> (DRAFT for issue #3)
#
# Fail closed: any gitleaks finding quarantines the run; nothing reaches clean/.
# Regex redaction is defense in depth on top of gitleaks, not a replacement.
set -uo pipefail
raw="${1:?usage: trace-scrub.sh RAW_RUN_DIR}"
root="${GIBSON_TRACE_ROOT:-$HOME/gibson-traces}"
rel="${raw#"$root"/raw/}"
[[ "$rel" != "$raw" ]] || { echo "not under $root/raw: $raw" >&2; exit 2; }
clean="$root/clean/$rel"; quar="$root/quarantine/$rel"

if command -v gitleaks >/dev/null; then
  if ! gitleaks detect --no-git --source "$raw" --redact --no-banner --exit-code 1 \
        --report-path "$raw/.gitleaks.json" >/dev/null 2>&1; then
    mkdir -p "$(dirname "$quar")" && cp -R "$raw" "$quar"
    echo "quarantined (gitleaks finding): $rel" >&2; exit 3
  fi
else
  # No gitleaks = no clean copy. Fail closed.
  mkdir -p "$(dirname "$quar")" && cp -R "$raw" "$quar"
  echo "quarantined (gitleaks not installed): $rel" >&2; exit 4
fi

mkdir -p "$clean"
home_re="$(printf '%s' "$HOME" | sed 's/[][\.*^$/]/\\&/g')"
for f in "$raw"/*; do
  [[ -f "$f" ]] || continue
  case "$(basename "$f")" in .gitleaks.json|.started) continue ;; esac
  sed -E \
    -e "s#${home_re}#~#g" \
    -e 's#/(Users|home)/[A-Za-z0-9._-]+#~#g' \
    -e 's#[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}#<email>#g' \
    -e 's#([Bb]earer)[[:space:]]+[A-Za-z0-9._~+/=-]{12,}#\1 <redacted>#g' \
    -e 's#([A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)(["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?)[^"'"'"'[:space:],}]+#\1\3<redacted>#g' \
    -e 's#(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^[:space:]"'"'"']+#\1://<redacted>#g' \
    -e 's#(sk|pk|rk)-[A-Za-z0-9_-]{16,}#<redacted-key>#g' \
    -e 's#gh[pousr]_[A-Za-z0-9]{20,}#<redacted-gh>#g' \
    "$f" > "$clean/$(basename "$f")"
done

# Injection flags are recorded, not dropped (issue #3 AC3). Path is relative to the Gibson checkout.
if [[ -n "${GIBSON_ROOT:-}" && -x "$GIBSON_ROOT/scripts/injection-scan.sh" ]]; then
  if ! "$GIBSON_ROOT/scripts/injection-scan.sh" "$clean" >/dev/null 2>&1; then
    [[ -f "$clean/record.json" ]] && jq '.labels.injection_flagged=true' "$clean/record.json" > "$clean/.r" && mv "$clean/.r" "$clean/record.json"
  fi
fi
chmod -R go-rwx "$clean"
echo "clean: $rel"
