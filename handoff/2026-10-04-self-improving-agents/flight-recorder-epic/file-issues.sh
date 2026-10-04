#!/usr/bin/env bash
# file-issues.sh — file the flight-recorder epic + 6 children on GitHub as P0/P1.
# Run from your Mac (needs gh auth):  ./file-issues.sh [owner/repo]   (default The-AIE/the-gibson)
# Dry run:                             DRY_RUN=1 ./file-issues.sh
set -euo pipefail
REPO="${1:-The-AIE/the-gibson}"
cd "$(dirname "$0")"
run() { if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ $*"; else "$@"; fi; }

ensure_label() {  # create only if missing; never recolor existing labels
  gh label list -R "$REPO" --limit 500 --json name -q '.[].name' | grep -qx "$1" || run gh label create "$1" -R "$REPO" --color "$2" >/dev/null
}
for l in gibson:5319e7 tier-a:c5def5 tier-b:fbca04 tier-c:b60205 P0:b60205 P1:d93f0b area:observability:0e8a16 area:loop:0e8a16 area:security:b60205 area:research:1d76db; do
  ensure_label "${l%:*}" "${l##*:}"
done

echo "Filing to $REPO"; [[ "${DRY_RUN:-0}" == "1" ]] || { read -r -p "Proceed? [y/N] " ok; [[ "$ok" == "y" ]] || exit 1; }

declare -a NUMS
for f in issues/0*.md; do
  title="$(head -1 "$f" | sed 's/^# //')"
  labels="$(grep -m1 '^Labels:' "$f" | sed 's/^Labels: //; s/`//g; s/ //g')"
  body="$(tail -n +2 "$f" | grep -v '^Labels:')"
  if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ gh issue create -R $REPO -t \"$title\" -l $labels"; NUMS+=("#?"); continue; fi
  url="$(gh issue create -R "$REPO" -t "$title" -l "$labels" -b "$body")"
  NUMS+=("#${url##*/}"); echo "filed $title → $url"
done

epic_title="$(head -1 EPIC.md | sed 's/^# //')"
epic_labels="$(grep -m1 '^Labels:' EPIC.md | sed 's/^Labels: //; s/`//g; s/ //g')"
epic_body="$(tail -n +2 EPIC.md | grep -v '^Labels:')"
map=""; i=1; for n in "${NUMS[@]}"; do map+="- child $i → $n"$'\n'; i=$((i+1)); done
epic_body="$epic_body"$'\n\n## Filed children\n'"$map"
run gh issue create -R "$REPO" -t "$epic_title" -l "$epic_labels" -b "$epic_body"
echo "Done. Children #1–#3 are P0: assign #3 (scrub/store) first. It blocks the rest."
