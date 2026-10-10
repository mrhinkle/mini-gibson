# Handoff review — 2026-10-04 (Claude Code)

Reviewed `mini-gibson-handoff-2026-10-04.zip` against the live repos, both machines, and the three CLIs.
All 49 package tests pass (20 tools, 18 verifier, 11 capture, now 12 with real fixtures).

## Findings that change the plan

### 1. The data gap is mostly not real. Historical trajectories already exist on disk.
§4 says "no tool-call trajectories anywhere." The CLIs keep their own session logs:

| Store | Mac | Mini |
|---|---|---|
| `~/.codex/sessions` | 3.4 GB, 2,191 rollouts | 1.2 GB, 1,150 |
| `~/.grok/sessions` | 2.0 GB, 9,223 files | 212 MB, 469 |
| `~/.claude/projects` | 3.1 GB, 3,922 | 62 MB, 202 |

`draft/history_inventory.py` (metadata only, writes to `~/gibson-traces/inventory/`, 0700) found
**2,521 sessions** tied to Gibson, ConferenceOS, or Chatterbuilt. **2,068** have 5+ tool calls
(about 60k tool calls), dated Jul–Oct 2026. Joined to PRs:

- ~520 sessions match a PR head branch exactly; ~395 of those are merged ConferenceOS PRs (Codex).
- 251 distinct PRs have at least one joined session (COS 204, Gibson 26, Chatterbuilt 21).
- Unjoined: 879 Gibson Codex sessions on the Mini (probably Carmack-era reviewer/worker runs on
  scratch cwds) and 195 COS Grok sessions in named lanes. Both can be resolved by timestamp
  against lane worktree history.

Caveat: a branch match includes review sessions on that branch, not just builds. Role classification
(builder / reviewer / repair) is the next step before any training use.

**Implication:** the flight recorder doesn't need to be live by Monday for the hackathon.
Historical sessions joined to PR outcomes and CI cover the target of 300–500 trajectories
several times over. The recorder is still worth building, but as normal Gibson work, not as an
emergency Tier C change to `loop.sh` landing in one day through Carmack, an E3 review, and Mark's merge.

### 2. Three parallel plans for the same entry, and the handoff only knows about one
- **This package** (verifier + Jev sensor + flight recorder).
- **`The-AIE/the-gibson`**: #414 (corpus + Bench v0.1), #415 / draft PR #416 (env + GibsonEnv),
  #417 (design freeze, Claude-led Kimi/GLM steelman), #430 (Jev decision service, *agent-claimed today*).
- **`mrhinkle/mini-gibson`** (private, created today): PLAN.md on PR #5, master plan #1, Lane A
  Mark+Codex (#2), Lane B **John Willis**+Grok (#3, owns `bench/ training/ scripts/data/`), steelman gate #4.

Jev is being built **four times**: `jev_sensor.py` here, Gibson #430, mini-gibson PR #6, and PR #7.
Pick one. mini-gibson PR #7 (with causal-policy guards) looks like the newest.

**Recommendation:** treat `mrhinkle/mini-gibson` as canonical. Fold this package in as inputs:
`verify.py` and `jev_sensor.py` go to Lane A, while the inventory, converter, and fixtures go to Lane B
(John). Don't file the flight-recorder epic until that's settled.

### 3. Codex is broken on both machines, and Lane A is "Mark + Codex"
- Mac (codex-cli 0.154.0): `model = "gpt-6.1-sol"` → 400 "not supported when using Codex with a ChatGPT account."
- Mini (0.145.0): `model = "gpt-6-astra"` → 400 "requires a newer version of Codex."
- It works on the Mac with `-m gpt-6-astra -c service_tier=default`. On the Mini the fix is a CLI upgrade.
  Both are config or install changes I left for Mark. The Mini also runs Gibson's Codex reviewer lane.

### 4. §8 CLI checks: all resolved
| Item | Result |
|---|---|
| `claude -p --output-format stream-json --verbose` | Works (2.1.289, Mac + Mini) |
| `codex exec --json` | Works. Events: `thread.started`, `turn.*`, `item.started/completed` with `agent_message`, `command_execution` (`aggregated_output`, `exit_code`). The draft converter parsed it unchanged. |
| Grok structured output | **Exists.** `--output-format streaming-messages-json` emits Anthropic Messages NDJSON and works with loop.sh's exact `--prompt-file … --permission-mode bypassPermissions` call. The `~/.grok` file-copy fallback is gone. That fallback also risked copying arbitrary `~/.grok` files into the store. |
| Nemotron LoRA on Brev, hackathon rules, Jev limits | Not checked (needs Brev, Discord, or a key) |

### 5. Smaller corrections
- §4 says AB-219 is "barely run… no raw diffs yet." Issue #219 says the raw arm is complete (12/12)
  and the harness arm has 4 left. `paper/experiment/diffs-harness/` is untracked in the local Gibson checkout.
- `file-issues.sh` would create 7 new labels (`P0`, `P1`, `area:*`) the repo doesn't use. The repo
  uses `tier-*`, `epic`, `dependency-blocked`, and `dispatch-ready`. Also, `gh issue create -b "$body"` puts the body in argv. That's fine for these files, but it goes against the package's own no-argv rule for content in general.
- The memory budget (300–500 trajectories) was a Claude estimate, not a measured requirement.

## What changed in this branch (`claude/historical-inventory`)
- `draft/history_inventory.py`: new. Metadata-only session inventory, refuses to write inside a git worktree.
- `draft/trace.sh`: Grok capture uses `streaming-messages-json`. The Claude and Codex VERIFY notes are resolved.
- `draft/trace_export.py`: Grok tool names in `TOOL_MAP` (v2), Grok byte-array tool output decoded,
  `events.grok.jsonl` routed.
- `tests/fixtures/{claude,codex,grok}.real.jsonl`: real runs, trimmed to conversation events, paths
  scrubbed, gitleaks clean. Plus a test across all three vendors.
- Not run: the Snyk scan (Snyk MCP isn't signed in on this Mac).

## Proposed next steps
1. Mark: choose the canonical repo (recommend `mrhinkle/mini-gibson`) and the one Jev implementation.
2. Mark: fix Codex (Mac: set the model to `gpt-6-astra`; Mini: upgrade codex-cli).
3. Lane B: classify the joined sessions by role, then convert 25 candidates to the gold format using `trace_export.py`.
4. Run the scrub (`trace-scrub.sh`, fail-closed) before any converted session leaves `~/gibson-traces`.
5. File the flight-recorder epic later, as ordinary Tier C Gibson work through Carmack, not as a Monday P0.
