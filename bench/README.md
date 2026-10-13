# Gibson Bench v0.1

Frozen at `2026-10-13T14:50:29Z`. Status stays `FROZEN_v0.1` in
`manifest.v0.1.json`. `freeze_required_before_lora` stays true: these
tasks are a holdout, and a LoRA train set must not include them.

Synthetic fixture batches did not discriminate the model (about 92–97% of
those runs verified). v0.1 is real repository work: a candidate patch is
resolved only when the task's fail-to-pass tests go from red to green and
the pass-to-pass tests stay green.

Round 1 froze nine conference-os tasks. Round 2, the same day, adds 26
tasks under `external_holdout_unseen`. The original nine directories,
their labels, and their manifest hashes are unchanged. `bench/verify.py`
is unchanged.

## What is frozen

35 tasks. `development` and `validation` are empty.

| Task | Split | Type | Fail-to-pass | Pass-to-pass | Budget |
| --- | --- | --- | ---: | ---: | ---: |
| conference-os-2244 | temporal_gibson_holdout | bug fix | 4 | 3 | 90s |
| conference-os-2247 | temporal_gibson_holdout | bug fix | 1 | 6 | 90s |
| conference-os-2250 | temporal_gibson_holdout | bug fix | 1 | 50 | 90s |
| conference-os-2260 | temporal_gibson_holdout | bug fix | 17 | 0 | 90s |
| conference-os-2263 | temporal_gibson_holdout | bug fix | 1 | 42 | 90s |
| conference-os-2264 | temporal_gibson_holdout | bug fix | 7 | 138 | 90s |
| conference-os-2266 | external_holdout | bug fix | 17 | 0 | 90s |
| conference-os-2274 | external_holdout | bug fix | 1 | 25 | 90s |
| conference-os-2275 | external_holdout | bug fix | 1 | 6 | 90s |
| the-gibson-78 | external_holdout_unseen | sensor | 9 | 33 | 90s |
| the-gibson-122 | external_holdout_unseen | sensor | 6 | 147 | 90s |
| the-gibson-203 | external_holdout_unseen | bug fix | 3 | 13 | 90s |
| the-gibson-270 | external_holdout_unseen | sensor | 5 | 13 | 90s |
| the-gibson-338 | external_holdout_unseen | sensor | 2 | 69 | 90s |
| the-gibson-398 | external_holdout_unseen | sensor | 2 | 57 | 90s |
| the-gibson-125 | external_holdout_unseen | feature | 2 | 13 | 90s |
| the-gibson-131 | external_holdout_unseen | feature | 10 | 1 | 90s |
| chatterbuilt-352 | external_holdout_unseen | sensor | 5 | 19 | 90s |
| chatterbuilt-329 | external_holdout_unseen | feature | 2 | 2 | 90s |
| chatterbuilt-332 | external_holdout_unseen | feature | 3 | 6 | 90s |
| chatterbuilt-477 | external_holdout_unseen | feature | 3 | 20 | 90s |
| chatterbuilt-545 | external_holdout_unseen | feature | 350 | 48 | 90s |
| conference-os-1931 | external_holdout_unseen | bug fix | 3 | 5 | 90s |
| conference-os-1934 | external_holdout_unseen | bug fix | 15 | 5 | 90s |
| conference-os-1954 | external_holdout_unseen | bug fix | 2 | 11 | 90s |
| conference-os-2030 | external_holdout_unseen | bug fix | 14 | 3 | 90s |
| conference-os-2047 | external_holdout_unseen | bug fix | 11 | 13 | 90s |
| conference-os-2048 | external_holdout_unseen | bug fix | 5 | 0 | 90s |
| conference-os-2049 | external_holdout_unseen | bug fix | 3 | 0 | 90s |
| conference-os-2054 | external_holdout_unseen | bug fix | 2 | 2 | 90s |
| conference-os-2056 | external_holdout_unseen | bug fix | 1 | 3 | 90s |
| conference-os-1940 | external_holdout_unseen | feature | 43 | 0 | 90s |
| conference-os-2023 | external_holdout_unseen | feature | 14 | 22 | 90s |
| conference-os-2042 | external_holdout_unseen | feature | 21 | 46 | 90s |
| conference-os-2197 | external_holdout_unseen | feature | 15 | 39 | 90s |

Counts by repository: conference-os 22 (9 from round 1, 13 new), the-gibson
8, chatterbuilt 5. Counts by type among the 26 new tasks: bug fix 10,
feature 10, sensor hardening 6. The sensor tasks are shell or vitest
contracts (claim dates, release preflight, suite timeout, silent-noop
hasher, numstat parsing, residual-honesty strings).

Six of the original tasks are `temporal_gibson_holdout` (the pull request
has a session in historical-v7 and is not in train-v7). Three are
`external_holdout` (merged after the train cutoff and absent from
historical-v7). The 26 new tasks are `external_holdout_unseen`.

`gold.patch` is the product diff. `task.json` marks it
`never_shown_to_agent`. `test.patch` is applied by the verifier, not by the
agent. Each task directory is hashed in the manifest (sha256 of sorted
relative paths, a NUL, the file bytes, and a NUL).

## How tasks were selected

### Round 1

Train-v7 only contains pull requests merged before
`2026-10-12T02:26:20Z`. The first candidate window was pull requests merged
after that cutoff, plus the 12 designated holdout pull requests (all
conference-os: 2241, 2245, 2246, 2248, 2250, 2251, 2253, 2263, 2264, 2265,
2269, 2270).

`gh pr list --state merged --search "merged:>=2026-10-12"` is date-grained,
so it also returned three conference-os pull requests merged earlier that
calendar day (2239, 2240, 2243). Those are inside the train window and are
not holdouts. They were not candidates.

### Round 2

Coordinator decision (Claude, 2026-10-13): contamination is defined by the
LoRA's training data, not by the merge date. A pull request can enter
`external_holdout_unseen` when all of these hold:

- It is merged in `The-AIE/the-gibson`, `The-AIE/chatterbuilt`, or
  `The-AIE/conference-os` on or after 2026-08-01, so the code matches
  current conventions.
- Its `(repo, pr)` is absent from `~/gibson-traces/sft/train-v7.jsonl`.
  Only `repo`, `pr`, and issue fields were read.
- It shares no linked issue with a train-v7 pull request. The key is
  `(repo, issue)`. Closing issues were expanded the same way as the
  historical holdout. The same issue number in two repositories is two
  issues. Train pull request chatterbuilt 679 closes issues 673 and 676,
  so 676 is a train issue even though it is not the episode's primary issue.
- The linked issue statement is at least 200 characters. Every kept
  statement came from the issue. Diff fences were removed. Statements are
  truncated at 4,000 characters. Nothing was copied out of the patch as a
  hint.
- A fail-to-pass check runs offline, twice on each side, in under five
  minutes, with `gold.patch` and `test.patch`. A public-scan hit in the
  problem statement, either patch, or a test id drops the candidate. The
  text is left as it was.

The base commit (`baseRefOid`) is checked out in a temporary worktree. The
diff is `gh pr diff` applied onto that base. Test-file changes are applied
alone and must fail. The full diff is applied and the same tests must pass.
Existing tests in the touched files that pass on both sides are
pass-to-pass. A second identical run is required. Any regression, a
non-zero exit after the full patch, or a second run that disagrees drops
the candidate.

the-gibson is scored by running the one suite file the pull request
touches: `bash scripts/tests/<suite>.test.sh`. `scripts/tests/run-all.sh
--only <suite>` still executes about 149 seconds of preamble and then
prints a one-line tally, so it hides the assertion names the verifier
needs. Suites that cannot finish inside the verifier's 300 second cap were
left out of the scored pool. Qualification allowed up to 600 seconds a
side while searching. Every kept task finished in under 20 seconds, so
`time_budget_s` is 90. `verify.py` was not edited, and it still rejects a
budget above 300.

chatterbuilt and conference-os are scored with vitest on the unit files the
pull request touches. End-to-end, Playwright, Prisma, and network tests are
out. Chatterbuilt runs from the repository root:

```bash
node_modules/.bin/vitest run --config vitest.config.ts --root <app> \
  --reporter=json --outputFile <logs>/vitest.json \
  lib/<file>.test.ts
```

The filter path is relative to the app root. One app per command. The
verifier accepts one `node_modules` directory per repository, so every
chatterbuilt task, including the marketing task, uses
`apps/mcp/node_modules`.

`gh pr list` for conference-os stopped at 400 merged pull requests. The
oldest merge in that page is `2026-08-24T10:23:08Z`. Earlier August merges
are outside this freeze.

The keep target was 30 tasks total and at least 7 per repository where the
pool could produce them. Examination stopped at 40 candidates per
repository, or earlier once a repository had 8 kept tasks. Every candidate
that passed was kept. The freeze is 35 tasks: the original 9 plus 26.
Chatterbuilt stayed at 5.

## Exclusions

### Round 1, post-cutoff window

Chatterbuilt: the merged search returned no pull requests. Zero tasks.

the-gibson: 3 candidates, 0 tasks.

| Pull request | Why it is out |
| --- | --- |
| 477 | One check regressed after the full patch. The patch also contains host paths and a personal login, which the public-bound scan rejects. |
| 478 | `scripts/tests/contract-authority.test.sh` did not finish within 240 seconds on the base checkout. |
| 479 | Same suite, same timeout on the base checkout. |

conference-os: 24 candidates, 9 tasks.

| Count | Pull requests | Why they are out |
| ---: | --- | --- |
| 4 | 2248, 2253, 2269, 2270 | Test-only diffs. There is no product patch for the agent to write. |
| 2 | 2249, 2259 | Empty diffs (merge commits with no file changes). |
| 1 | 2265 | Documentation only. No vitest file. |
| 1 | 2267 | Image and video assets only. No vitest file. |
| 1 | 2268 | Touched unit tests already passed on the base. Not fail-to-pass. |
| 5 | 2245, 2246, 2251, 2262, 2285 | Patch or test ids contain email addresses or a personal login. |
| 1 | 2241 | Qualified behaviorally, then removed. Diff context contains placeholder secret-key literals. Rewriting those context lines makes `git apply` fail, so the task cannot ship in a public-bound tree. |

### Round 2, merged on or after 2026-08-01

Fetched with `gh pr list --limit 400 --state merged --search "merged:>=2026-08-01"`.

| Repository | Fetched | Candidates | Scored pool | Examined | Kept |
| --- | ---: | ---: | ---: | ---: | ---: |
| the-gibson | 172 | 107 | 54 | 11 | 8 |
| chatterbuilt | 165 | 59 | 47 | 40 | 5 |
| conference-os | 400 | 255 | 210 | 40 | 13 |

Prefilter, before any test run. Counts are per repository.

| Reason | the-gibson | chatterbuilt | conference-os |
| --- | ---: | ---: | ---: |
| Already in the frozen nine | 0 | 0 | 9 |
| Pull request is in train-v7 | 2 | 24 | 32 |
| Shares a linked issue with a train-v7 pull request | 0 | 1 | 0 |
| Empty file list | 0 | 0 | 2 |
| Docs or assets only | 36 | 64 | 13 |
| No test file | 24 | 15 | 66 |
| Test-only diff | 3 | 2 | 23 |

The scored pool is narrower than the candidate list:

| Reason | the-gibson | chatterbuilt | conference-os |
| --- | ---: | ---: | ---: |
| Not a single shell suite | 39 | 0 | 0 |
| Suite excluded as slower than the 300s verifier cap | 14 | 0 | 0 |
| Tests sit outside apps/mcp, apps/dashboard, apps/prospecting, and marketing | 0 | 11 | 0 |
| Tests span two app roots, so one vitest command cannot score them | 0 | 1 | 0 |
| No `tests/unit/*.test.ts` file | 0 | 0 | 37 |
| Unit file name matches prisma, migrat, neon, or idempoten | 0 | 0 | 8 |

Slow the-gibson suites left unscored: `release-claim`, `contract-authority`,
`loop-fleet`, `architecture-fitness`, `policy-manifest`,
`bash32-syntax-each`, `git-configure`.

Examined and dropped. the-gibson stopped at 8 kept tasks (11 examined of
54). chatterbuilt and conference-os hit the 40-candidate cap.

| Reason | the-gibson | chatterbuilt | conference-os |
| --- | ---: | ---: | ---: |
| Kept | 8 | 5 | 13 |
| Patch contains an email address | 1 (119) | 15 | 8 |
| Patch contains a personal login | 1 (325) | 11 | 0 |
| Patch contains a host path | 0 | 1 (541) | 0 |
| Patch contains a GitHub personal-access token prefix | 0 | 1 (530) | 0 |
| Problem statement contains a personal login | 0 | 4 | 2 (2041, 2034) |
| Test id contains an email address | 0 | 0 | 1 (1903) |
| Tests still fail after the full patch | 0 | 3 (354, 643, 529) | 16 |
| Base run exceeded the search timeout | 1 (151, `loop-state.test.sh` called `gh`) | 0 | 0 |

No kept task shares a pull request or a linked issue with train-v7, with
the frozen nine, or with another kept task. Zero of the chatterbuilt
candidates shared train issue 676 after that issue was added to the train
set.

## Verifier

```bash
python3 bench/verify.py TASK_ID CANDIDATE_PATCH
```

The process prints one JSON object:

```json
{"resolved": false, "f2p_pass": false, "p2p_pass": false, "logs_path": "..."}
```

Exit 0 only when `resolved` is true. `resolved` is true only when every
fail-to-pass id passed and every pass-to-pass id passed. Any setup failure
(missing mirror, unknown commit, patch that will not apply, setup command
failure, missing runner output, time-budget expiry, cleanup failure) sets
`error` and `resolved` to false. A setup failure is never resolved.

`time_budget_s` must be from 1 through 300. That cap is why the slow
the-gibson suites above are excluded.

Environment, never written into task files:

- `GIBSON_BENCH_MIRRORS`: JSON object of repository name to a local git checkout.
- `GIBSON_BENCH_NODE_MODULES`: optional JSON object of repository name to a `node_modules` directory. The verifier symlinks it into the temporary worktree when the checkout has none. Chatterbuilt's value is `apps/mcp/node_modules` for every chatterbuilt task.

Commands use `<repo-root>`, `<mirror>`, and `<logs>`. The scored child drops
environment variables whose names contain `TOKEN`, `SECRET`, `PASSWORD`,
`DATABASE_URL`, `POSTGRES`, `API_KEY`, or `OPENROUTER`.

conference-os-2250 runs `node_modules/.bin/prisma generate` during setup,
before either patch. That writes the generated client into the worktree. It
does not open a database. The schema is unchanged by the pull request.

Shell tasks parse `ok   — name` and `FAIL — name` lines. The id prefix is
the first `scripts/tests/*.test.sh` in the command. A non-zero suite exit
fails `__suite__`.

## Known limits

- Chatterbuilt yielded 5 tasks from 40 examined candidates, short of 7. Most drops were public-scan hits. The search stopped at the cap.
- Conference-os merges from 2026-08-01 through 2026-08-23 are outside the 400-row page.
- `node_modules` is not in this repository. A checkout without `GIBSON_BENCH_NODE_MODULES` cannot run the vitest tasks. the-gibson shell tasks do not need it.
- End-to-end, Playwright, network, and database tests are not in the scored set.
- conference-os-2250 and conference-os-2263 share issue 2235. conference-os-2260 and conference-os-2266 share issue 2258. Issue 2272, used by conference-os-2274, states the one-line content-security-policy change in the issue itself.
- conference-os-2260, conference-os-2266, conference-os-1940, conference-os-2048, and conference-os-2049 have an empty pass-to-pass list.
- One comment in conference-os-2275 `gold.patch` that named a private repository owner was rewritten to "a public repository (pull request 185)". The tests do not assert that comment. `gold.patch` is still never shown to the agent. Round 2 did not rewrite patches.
- The verifier runs each task's commands once. These tasks each have one command shared by fail-to-pass and pass-to-pass.
- the-gibson-122's slowest qualification run was 19.3 seconds. The other new tasks finished in under 10 seconds. The budget is 90 seconds for every task.
- Setup runs on the base commit, before either patch. the-gibson-131 adds `scripts/tests/formal-review.test.sh` in `test.patch`, so its setup checks that `scripts/tests` exists.
