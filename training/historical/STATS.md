# Historical SFT corpus stats

Generated: 2026-10-13T09:48:54Z
Output: ~/gibson-traces/sft/historical-v6.jsonl (all roles on merged PRs, mode 600).
Train: ~/gibson-traces/sft/train-v6.jsonl (builder only, temporal holdout removed, mode 600).
Holdout: ~/gibson-traces/sft/holdout-v6.jsonl (builder episodes on the latest PRs, mode 600).
Negatives: ~/gibson-traces/sft/negatives-v6.jsonl (builders on closed-unmerged PRs, mode 600).
Assessor: ~/gibson-traces/sft/assessor-v6.jsonl (reviewers on merged PRs with a verdict, mode 600).
Source: Mac and Mini sessions joined to a pull request.
Token estimate: 4 characters per token. Tool outputs over 4096 tokens are truncated.
Episodes over 32768 tokens are split into windows that each keep the system and user task.

## Against the 300 target

| Metric | Count |
| --- | ---: |
| Usable episodes (sessions that produced a kept window) | 1335 |
| Builder episodes on merged PRs | 131 |
| Training windows written | 2515 |
| Target episodes | 300 |
| Stretch band | 300–500 |
| Gap to 300 episodes | 169 |

## Selection and drops

| Reason | Count |
| --- | ---: |
| Selected merged sessions | 1384 |
| Missing file | 1 |
| Unreadable | 0 |
| Parse error | 0 |
| No grok chat_history | 1 |
| Empty trajectory | 47 |
| Dropped, residual secret | 0 |
| Dropped, schema | 0 |
| Groups or windows over the episode cap | 0 |
| PR metadata missing | 0 |
| Issue task fetched from GitHub | 900 |
| Issue task from PR metadata body | 0 |
| Issue task fallback, old header | 435 |

Residual pattern hits on dropped sessions and on windows rejected inside a kept session (names only):

| Pattern | Hits |
| --- | ---: |
| home_path | 4 |

## Truncation and windowing, both ways

| | Episodes | Windows |
| --- | ---: | ---: |
| Within 32768 tokens after tool truncation | 526 | 526 |
| Over 32768 tokens, split | 809 | 1989 |
| Total kept | 1335 | 2515 |

| Tool outputs | Count |
| --- | ---: |
| Seen | 32046 |
| Truncated above 4096 tokens | 5012 |
| Left whole | 27034 |
| Estimated tokens in tool outputs before truncation | 58467580 |
| Estimated tokens in tool outputs after truncation | 40829906 |
| Orphan tool results skipped while windowing | 9 |

Sum of window token_count estimates: 59689580

## By repo (episodes / windows)

| Repo | Episodes | Windows |
| --- | ---: | ---: |
| chatterbuilt | 244 | 457 |
| conference-os | 977 | 1829 |
| the-gibson | 114 | 229 |

## By role (episodes / windows / tokens)

| Role | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| builder | 131 | 349 | 8885202 |
| reviewer | 1109 | 2022 | 47796965 |
| other | 95 | 144 | 3007413 |

## Splits

Sample seed: 414
Train token cap: 16000000
Holdout fraction of builder PRs: 0.15
Holdout cutoff (earliest date-based mergedAt kept out): 2026-10-12T02:11:18Z
Builder PRs: 77
Holdout PRs: 13
Holdout PRs added by shared issue: 1
Holdout/train PR overlap: 0
Holdout/train episode overlap: 0
Holdout/train issue overlap: 0
Windows dropped for a residual on the joined text: 4

| Split | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| historical-v6, all roles | 1335 | 2515 | 59689580 |
| holdout-v6, builder, latest PRs plus issue lineage | 17 | 46 | 1198987 |
| train pool, builder, not held out | 114 | 303 | 7686215 |
| train-v6, after sampling | 114 | 303 | 7686215 |
| builder pool left out by the cap | 0 | 0 | 0 |
| negatives-v6, builder, closed-unmerged | 25 | 61 | 1587920 |
| assessor-v6, reviewer with verdict | 637 | 1093 | 25379082 |

### Train by repo

| Repo | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| chatterbuilt | 46 | 138 | 3655561 |
| conference-os | 65 | 160 | 3919764 |
| the-gibson | 3 | 5 | 110890 |

### Holdout by repo

| Repo | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| conference-os | 17 | 46 | 1198987 |

## By vendor (episodes / windows)

| Vendor | Episodes | Windows |
| --- | ---: | ---: |
| claude | 26 | 31 |
| codex | 979 | 1798 |
| grok | 330 | 686 |

## Secret re-scan of the output file

Hits: 0

## Output validation

JSONL records: 2515
Bad JSON lines: 0
Schema error codes: {}

## Join method by role, repo, and vendor

| Join method | Role | Repo | Vendor | Episodes | Windows | Tokens |
| --- | --- | --- | --- | ---: | ---: | ---: |
| branch | other | chatterbuilt | claude | 13 | 13 | 221167 |
| branch | other | chatterbuilt | codex | 1 | 6 | 186768 |
| branch | other | conference-os | codex | 1 | 1 | 223 |
| branch | reviewer | chatterbuilt | claude | 1 | 1 | 572 |
| branch | reviewer | chatterbuilt | codex | 75 | 111 | 2276304 |
| branch | reviewer | conference-os | codex | 582 | 1059 | 25214716 |
| branch | reviewer | the-gibson | claude | 2 | 2 | 42223 |
| branch | reviewer | the-gibson | codex | 33 | 47 | 983838 |
| commit | builder | chatterbuilt | grok | 3 | 8 | 207316 |
| coverage | builder | chatterbuilt | grok | 6 | 11 | 287415 |
| coverage | builder | conference-os | grok | 2 | 2 | 56870 |
| coverage | builder | the-gibson | grok | 3 | 6 | 156406 |
| issue-merged-unique | builder | the-gibson | grok | 2 | 2 | 46690 |
| issue-merged-unique | reviewer | conference-os | grok | 5 | 10 | 229714 |
| issue-merged-unique | reviewer | the-gibson | codex | 4 | 6 | 83031 |
| issue-merged-unique | reviewer | the-gibson | grok | 1 | 2 | 50013 |
| issue | builder | chatterbuilt | grok | 5 | 15 | 359974 |
| issue | builder | conference-os | grok | 15 | 31 | 745564 |
| issue | other | chatterbuilt | codex | 1 | 1 | 15137 |
| issue | other | chatterbuilt | grok | 6 | 9 | 168134 |
| issue | other | conference-os | grok | 5 | 10 | 204445 |
| issue | reviewer | chatterbuilt | codex | 11 | 14 | 232628 |
| issue | reviewer | conference-os | codex | 8 | 9 | 210705 |
| issue | reviewer | conference-os | grok | 14 | 20 | 465643 |
| issue | reviewer | the-gibson | codex | 2 | 3 | 51900 |
| prompt-branch | builder | chatterbuilt | grok | 1 | 3 | 88368 |
| prompt-branch | builder | conference-os | grok | 5 | 10 | 247770 |
| prompt-branch | other | chatterbuilt | grok | 1 | 1 | 10995 |
| prompt-branch | other | conference-os | grok | 1 | 2 | 38573 |
| prompt-branch | reviewer | conference-os | codex | 15 | 38 | 1020108 |
| prompt-branch | reviewer | conference-os | grok | 19 | 31 | 700140 |
| prompt-header | builder | chatterbuilt | grok | 38 | 116 | 3104431 |
| prompt-header | builder | conference-os | grok | 61 | 166 | 4150562 |
| prompt-header | builder | the-gibson | grok | 8 | 22 | 550566 |
| prompt-header | other | chatterbuilt | grok | 31 | 50 | 1079215 |
| prompt-header | other | conference-os | grok | 16 | 23 | 469810 |
| prompt-header | reviewer | chatterbuilt | grok | 25 | 60 | 1500298 |
| prompt-header | reviewer | conference-os | codex | 2 | 5 | 126399 |
| prompt-header | reviewer | conference-os | grok | 58 | 91 | 2149026 |
| prompt-pr | builder | chatterbuilt | grok | 3 | 10 | 274408 |
| prompt-pr | builder | the-gibson | claude | 1 | 3 | 64200 |
| prompt-pr | builder | the-gibson | grok | 3 | 5 | 132582 |
| prompt-pr | other | chatterbuilt | claude | 2 | 3 | 55464 |
| prompt-pr | other | chatterbuilt | grok | 9 | 13 | 288586 |
| prompt-pr | other | conference-os | claude | 2 | 2 | 26717 |
| prompt-pr | other | conference-os | grok | 1 | 1 | 30782 |
| prompt-pr | other | the-gibson | claude | 2 | 2 | 30914 |
| prompt-pr | other | the-gibson | grok | 3 | 7 | 180483 |
| prompt-pr | reviewer | chatterbuilt | codex | 17 | 27 | 700641 |
| prompt-pr | reviewer | chatterbuilt | grok | 5 | 10 | 193569 |
| prompt-pr | reviewer | conference-os | codex | 166 | 321 | 7612860 |
| prompt-pr | reviewer | the-gibson | claude | 3 | 5 | 93356 |
| prompt-pr | reviewer | the-gibson | codex | 61 | 150 | 3859281 |

## Unjoined sessions

| Join method | Sessions |
| --- | ---: |
| branch | 855 |
| commit | 3 |
| coverage | 11 |
| issue | 69 |
| issue-merged-unique | 12 |
| prompt-branch | 51 |
| prompt-header | 260 |
| prompt-pr | 349 |

| Unjoined reason | Sessions |
| --- | ---: |
| ambiguous_branch | 14 |
| ambiguous_issue | 211 |
| ambiguous_prompt | 865 |
| no_file_overlap | 32 |
| no_match | 178 |
| no_signal | 104 |

## Notes

The user task is the issue title plus the first 1500 characters of the issue body.
Bodies are fetched with gh issue view and cached under ~/gibson-traces/cache/.
When the fetch fails, the user task stays the PR number, branch, and linked issue number.
The session's own user messages follow that task.
session_role is builder, reviewer, or other, from the tool calls the session made.
A builder successfully edited or wrote a file, or ran git commit, in a session that was launched with write access.
The edit counts when its tool result shows the file changed.
A read-only sandbox, an `-s read-only` launch, or a reviewer prompt that says read-only is a reviewer.
Keyword evidence breaks a tie when the session neither edited successfully nor committed.
The train split keeps every the-gibson and chatterbuilt builder episode outside the holdout,
then fills the token cap with conference-os builder episodes, seeded and round-robin by vendor.
The holdout starts as the latest fraction of builder PRs by mergedAt.
A builder PR that shares an issue with one of those PRs is moved into the holdout.
The cutoff stays the earliest mergedAt among the date-based holdout PRs.
A pull request, an episode, or an issue in the holdout is absent from the train split.
Commit joins use SHAs the session created: git commit's [branch sha], or git rev-parse HEAD after that commit.
A SHA printed by git log, git show, or rev-parse of another ref is ignored.
That displayed SHA is kept when it equals a candidate pull request head or one of that pull request's commits.
commit-merged-unique and issue-merged-unique mean several pull requests shared a commit or an issue
and exactly one of them was merged. Any other ambiguous session stays unjoined.
The first user prompt can declare a branch or a PR number. That is prompt-branch or prompt-pr.
A declaration is read from that first prompt only. Later tool output is not a declaration.
The header is the first non-empty line of that prompt, or a line that starts with TASK.
When the header names exactly one branch, that branch wins. Otherwise one PR. Otherwise one issue in one repo.
Without a branch, that line must name exactly one number. PR #370 and #371 is two numbers, so it is not a header.
Numbers later in the prompt do not override the header. That join method is prompt-header.
A header the catalog cannot resolve does not fall through to those later numbers.
A branch the catalog misses can still use one PR or one issue written on that same header line.
When a prompt or an issue matches several pull requests, each candidate is scored by edit coverage,
the share of the session's successful edits that the pull request also changes.
The highest coverage wins when it is at least 0.5 and at least 0.2 above the next one.
Equal coverage prefers the candidate whose number appears on the header line. Otherwise the session stays ambiguous.
That join method is coverage. Jaccard is not used to choose a pull request.
A builder joined by a header, a prompt, or an issue must have at least 30% of its successful edits on that pull request.
That ratio is the share of the session's edits the pull request also changes, not Jaccard.
A merged pull request is the union of every session plus the coordinator commit, so Jaccard rejects a true subset.
An empty edit set scores 0. A builder below 0.3 is unjoined with reason no_file_overlap.
Joining a reviewer does not make that session a builder.
A session that still matches a secret pattern after redaction is dropped and counted.
The secret re-scan decodes each JSON line, checks each string, and checks the concatenation of message and tool strings.
A backslash added by JSON encoding is not itself a secret.
Provenance is the PR URL plus a hash of the session path. The raw path is not stored.
## Round 5 versus v3 (2026-10-13)

Sibling pull requests that share an issue with a date-held pull request go into the holdout. The closure is transitive. They are not dropped: the holdout is the eval set for that issue lineage, and dropping the sibling would hide the leak. The cutoff stays the earliest mergedAt of the date-based holdout. This rebuild added 0 lineage pull requests, so the cutoff is the date-based set alone: 2026-10-06T00:23:02Z (v3 cutoff was 2026-09-29T03:37:12Z, on a larger builder set).

| Measure | v3 | v4 | Delta |
| --- | ---: | ---: | ---: |
| Builder episodes on merged PRs | 256 | 92 | -164 |
| Train episodes | 222 | 71 | -151 |
| Holdout episodes | 34 | 21 | -13 |
| Historical windows | 2443 | 1855 | -588 |
| Historical episodes | 1244 | 993 | -251 |
| Builder PRs | 86 | 52 | -34 |
| Holdout PRs | 13 | 8 | -5 |
| Holdout PRs added by shared issue | 0 | 0 | 0 |
| Windows dropped for a residual on joined text | 0 | 4 | +4 |

Builder role flips, same episode id (same session, repo, and PR): 10. Eight became reviewer. Two became other. 193 v3 builder episode ids are absent from v4. 39 v4 builder episode ids were not builders in v3. 24 episodes moved from other to reviewer under the read-only launch rule.

Commit joins lost: 340 of 343 v3 commit joins. 72 fell through to an issue join (57 issue, 15 issue-merged-unique). 268 are unjoined (173 ambiguous_issue, 89 no_match, 6 no_signal). 3 stayed commit joins. 12 sessions that v3 left as ambiguous_commit became a unique commit join once displayed SHAs were ignored.

The 4 residual windows are home_path hits inside sessions that still produced other windows. A second redaction pass rewrote host paths (`../var/folders`, `file:///private/tmp`, `/System/Volumes`, bare `/Volumes`, escaped `/opt/homebrew`). The longer `<abs>/…` placeholder pushed 3 historical windows and 1 assessor window over the 32768-token cap; those windows were dropped. Train and holdout stayed under the cap. Final files: historical 993 episodes / 1855 windows, assessor 488 episodes / 847 windows. Substring scan of the rewritten files is 0.

## Round 6 versus v4 (2026-10-13)

Fleet builder sessions do not commit. The coordinator commits the diff afterward, so a session-created SHA is almost never available. v5 joins on the first prompt's declared branch or PR number, then on file overlap, and keeps the round-5 rule that a displayed SHA is not a commit the session created. The catalog is ~/gibson-traces/inventory/v2. v5 has 3012 sessions; v4 had 2999. Thirteen session files appeared after the v4 inventory.

Candidate picking among two or more prompt or issue PRs is still Jaccard, and it wins only at 0.5 or above and at least 0.2 above the next candidate. That fired 3 times. Builder confirm is a different ratio: the share of the session's successful edits that the pull request also changes, threshold 0.3. Jaccard against the merged PR rejects a session that edited a true subset, because the PR is the union of every session plus the coordinator commit. An empty edit set scores 0 and is `no_file_overlap`. Reviewers are not confirmed.

| Join label | v4 sessions | v5 sessions | Delta |
| --- | ---: | ---: | ---: |
| branch | 852 | 855 | +3 |
| prompt-branch | 0 | 259 | +259 |
| prompt-pr | 0 | 377 | +377 |
| commit | 15 | 4 | -11 |
| issue | 271 | 83 | -188 |
| issue-merged-unique | 47 | 14 | -33 |
| overlap | 0 | 3 | +3 |
| ambiguous_prompt | 0 | 873 | +873 |
| ambiguous_issue | 1335 | 219 | -1116 |
| ambiguous_branch | 14 | 14 | 0 |
| no_file_overlap | 0 | 32 | +32 |
| no_match | 351 | 172 | -179 |
| no_signal | 114 | 107 | -7 |

Most of the 873 `ambiguous_prompt` sessions were already unjoined in v4 (844 were `ambiguous_issue`). The opening prompt names more than one PR, and the file sets do not clear the Jaccard margin. A declared branch still beats a declared PR number. Later tool output is not read as a declaration.

| Measure | v4 | v5 | Delta |
| --- | ---: | ---: | ---: |
| Builder episodes on merged PRs | 92 | 130 | +38 |
| Train episodes | 71 | 113 | +42 |
| Train tokens | 5055913 | 7737103 | +2681190 |
| Holdout episodes | 21 | 17 | -4 |
| Holdout tokens | 1105641 | 1198987 | +93346 |
| Historical episodes | 993 | 1326 | +333 |
| Historical windows | 1855 | 2500 | +645 |
| Builder PRs | 52 | 75 | +23 |
| Holdout PRs | 8 | 13 | +5 |
| Holdout PRs added by shared issue | 0 | 1 | +1 |
| Builder pool left out by the 16M cap | 0 | 0 | 0 |

Holdout cutoff moved from 2026-10-06T00:23:02Z to 2026-10-12T02:11:18Z because the builder PR set grew. Seed 414, fraction 0.15, issue-lineage closure. One extra PR moved in by a shared issue. Train and holdout share 0 pull requests, 0 episodes, and 0 issues.

Train repo mix (episodes / tokens): chatterbuilt 44 / 3603408 (v4 24 / 2094748), conference-os 64 / 3923260 (v4 44 / 2735643), the-gibson 5 / 210435 (v4 3 / 225522). Holdout repo mix: conference-os 17 / 1198987. v4 holdout was chatterbuilt 13, conference-os 1, the-gibson 7. Historical repo mix (episodes): chatterbuilt 239 (v4 178), conference-os 971 (v4 728), the-gibson 116 (v4 87).

Merged builder episodes are still short of 300. The gap is 170.

## Round 7 versus v5 (2026-10-13)

v6 reads the opening-prompt header before the body. The header is the first non-empty line, or the first later line that starts with TASK. Exactly one branch on that line wins, including when the same line also names an issue or a prior-art PR. With no branch, the line must name exactly one number (one PR, or one issue in one repo). `PR #370 and #371` is two numbers and is not a header. A header the catalog misses does not adopt PR numbers from the rest of the prompt. A missing header branch can still use a PR or an issue on that same line. When two or more candidates remain, each is scored by edit coverage (the share of the session's successful edits that the pull request changes). The max wins only at 0.5 or above and at least 0.2 above the next. A tie on coverage prefers the candidate whose number is on the header line. That join method is `coverage`. Jaccard is not used to choose a pull request. The three v5 `overlap` joins kept their pull requests and are now `coverage`. Builder confirm stays 0.3 for header, prompt, and issue joins. A coverage pick is not confirmed again. Joining a reviewer leaves the role as reviewer.

v6 has 3014 sessions. v5 had 3012. The two new sessions are grok `no_match` rows that appeared after the v5 inventory. Counts below are the full inventories.

| Join label | v5 sessions | v6 sessions | Delta |
| --- | ---: | ---: | ---: |
| branch | 855 | 855 | 0 |
| prompt-header | 0 | 260 | +260 |
| prompt-branch | 259 | 51 | -208 |
| prompt-pr | 377 | 349 | -28 |
| commit | 4 | 3 | -1 |
| issue | 83 | 69 | -14 |
| issue-merged-unique | 14 | 12 | -2 |
| coverage | 0 | 11 | +11 |
| overlap | 3 | 0 | -3 |
| ambiguous_prompt | 873 | 865 | -8 |
| ambiguous_issue | 219 | 211 | -8 |
| ambiguous_branch | 14 | 14 | 0 |
| no_file_overlap | 32 | 32 | 0 |
| no_match | 172 | 178 | +6 |
| no_signal | 107 | 104 | -3 |

Of the 873 v5 `ambiguous_prompt` sessions, 11 resolved and 862 stayed `ambiguous_prompt`. Six resolved by `prompt-header` and five by `coverage`. 855 of the 862 that stayed are Codex sessions whose opening prompt names two or more PRs and does not carry a unique header target. The 7 grok sessions that stayed have no successful edits, so coverage cannot score them. Two of those seven are the `PR #370 and #371` lines, which the two-number rule leaves undecided.

On the 3012 sessions present in both inventories, 250 kept the same pull request and changed only the method label (200 `prompt-branch` to `prompt-header`, 26 `prompt-pr` to `prompt-header`, 15 `issue` to `prompt-header`, 6 `prompt-branch` to `issue`, 3 `overlap` to `coverage`). 31 sessions changed pull request. The header named a different branch, PR, or issue than the v5 join, or coverage picked among the PRs that one header issue closes. Two v5 `issue-merged-unique` joins on The-AIE/the-gibson#428 became `ambiguous_prompt` because header issue #424 closes two pull requests and coverage did not clear the margin. One v5 commit join on The-AIE/chatterbuilt#697 became `coverage` on #696 for the same reason (header issue #695 closes both). Two v5 prompt joins became `no_match` because the header named a branch or PR missing from the catalog and the body numbers were not used.

| Measure | v5 | v6 | Delta |
| --- | ---: | ---: | ---: |
| Builder episodes on merged PRs | 130 | 131 | +1 |
| Train episodes | 113 | 114 | +1 |
| Train tokens | 7737103 | 7686215 | -50888 |
| Holdout episodes | 17 | 17 | 0 |
| Holdout tokens | 1198987 | 1198987 | 0 |
| Historical episodes | 1326 | 1335 | +9 |
| Historical windows | 2500 | 2515 | +15 |
| Builder PRs | 75 | 77 | +2 |
| Holdout PRs | 13 | 13 | 0 |
| Holdout PRs added by shared issue | 1 | 1 | 0 |
| Builder pool left out by the 16M cap | 0 | 0 | 0 |

Holdout cutoff stayed 2026-10-12T02:11:18Z. Seed 414, fraction 0.15, issue-lineage closure. Train and holdout share 0 pull requests, 0 episodes, and 0 issues.

Train repo mix (episodes / tokens): chatterbuilt 46 / 3655561 (v5 44 / 3603408), conference-os 65 / 3919764 (v5 64 / 3923260), the-gibson 3 / 110890 (v5 5 / 210435). Holdout repo mix: conference-os 17 / 1198987, same as v5. Historical repo mix (episodes): chatterbuilt 244 (v5 239), conference-os 977 (v5 971), the-gibson 114 (v5 116).

Merged builder episodes are still short of 300. The gap is 169.

Ten of the 11 resolved sessions are in the v6 JSONL. The eleventh, `5883a9bd665d59c0-w00`, is `prompt-header` on The-AIE/the-gibson#477, which is OPEN, so the MERGED,CLOSED extract does not include it. Its header starts `TASK (Grok) — size round on /Users/mrhinkle/Code/the-gibson-wt/lane-160 (branch lane/160-delivery-receipt, PR The-AIE/th`. The five chatterbuilt#658 rows are reviewers. The two chatterbuilt#622 rows are builders in train. The three the-gibson#374 rows are builders in negatives (CLOSED).

| Episode | Method | PR | Header, first 120 characters |
| --- | --- | --- | --- |
| 80ac3fc0f605b604-w00 | prompt-header | chatterbuilt#658 | TASK (Grok, headless builder) — The-AIE/chatterbuilt issue #573, branch `feat/573-undo-apply-draft-pr`, worktree `/Users |
| 0ba37b4c9585f7d3-w00 | prompt-header | chatterbuilt#658 | TASK (Grok, headless builder) — The-AIE/chatterbuilt issue #573, branch `feat/573-undo-apply-draft-pr`, worktree `/Users |
| b6f67b3e85457b6d-w00 | prompt-header | chatterbuilt#658 | TASK (Grok, headless builder) — The-AIE/chatterbuilt issue #573, branch `feat/573-undo-apply-draft-pr`, worktree `/Users |
| fd22ed311c377d25-w00 | prompt-header | chatterbuilt#658 | TASK (Grok, headless builder) — The-AIE/chatterbuilt issue #573, branch `feat/573-undo-apply-draft-pr`, worktree `/Users |
| 068a61b6d8dd300b-w00 | prompt-header | chatterbuilt#658 | TASK (Grok, headless builder) — The-AIE/chatterbuilt issue #573, branch `feat/573-undo-apply-draft-pr`, worktree `/Users |
| 45020828334b26a3-w00 | coverage | chatterbuilt#622 | Coder task in existing PR #622 worktree /Users/mrhinkle/Documents/Codex/2026-09-09/le-2/work/lane-472-preview-guard. Do |
| ae4722f02f5aae1f-w00 | coverage | chatterbuilt#622 | You are the coder for issue #625 on the existing PR #622 worktree /Users/mrhinkle/Documents/Codex/2026-09-09/le-2/work/l |
| cf7c9cf5a1f9aceb-w00 | coverage | the-gibson#374 | # Grok implementation round 2 of 5 — issue #348 / PR #374 |
| 8dc15904d000fed9-w00 | coverage | the-gibson#374 | # Grok implementation round 3 of 5 — issue #348 / PR #374 |
| 4c54ced30553d7e0-w00 | coverage | the-gibson#374 | # Grok implementation round 4 of 5 — issue #348 / PR #374 |
