# Historical SFT corpus stats

Generated: 2026-10-13T04:18:22Z
Output: ~/gibson-traces/sft/historical-v3.jsonl (all roles on merged PRs, mode 600).
Train: ~/gibson-traces/sft/train-v3.jsonl (builder only, temporal holdout removed, mode 600).
Holdout: ~/gibson-traces/sft/holdout-v3.jsonl (builder episodes on the latest PRs, mode 600).
Negatives: ~/gibson-traces/sft/negatives-v3.jsonl (builders on closed-unmerged PRs, mode 600).
Assessor: ~/gibson-traces/sft/assessor-v3.jsonl (reviewers on merged PRs with a verdict, mode 600).
Source: Mac and Mini sessions joined to a pull request.
Token estimate: 4 characters per token. Tool outputs over 4096 tokens are truncated.
Episodes over 32768 tokens are split into windows that each keep the system and user task.

## Against the 300 target

| Metric | Count |
| --- | ---: |
| Usable episodes (sessions that produced a kept window) | 1244 |
| Builder episodes on merged PRs | 256 |
| Training windows written | 2443 |
| Target episodes | 300 |
| Stretch band | 300–500 |
| Gap to 300 episodes | 44 |

## Selection and drops

| Reason | Count |
| --- | ---: |
| Selected merged sessions | 1280 |
| Missing file | 0 |
| Unreadable | 0 |
| Parse error | 0 |
| No grok chat_history | 1 |
| Empty trajectory | 35 |
| Dropped, residual secret | 0 |
| Dropped, schema | 0 |
| Groups or windows over the episode cap | 0 |
| PR metadata missing | 0 |
| Issue task fetched from GitHub | 901 |
| Issue task from PR metadata body | 0 |
| Issue task fallback, old header | 343 |

Residual pattern hits on dropped sessions and on windows rejected inside a kept session (names only):

| Pattern | Hits |
| --- | ---: |
| env_assignment | 1 |
| home_path | 3 |
| home_path_encoded | 1 |

## Truncation and windowing, both ways

| | Episodes | Windows |
| --- | ---: | ---: |
| Within 32768 tokens after tool truncation | 441 | 441 |
| Over 32768 tokens, split | 803 | 2002 |
| Total kept | 1244 | 2443 |

| Tool outputs | Count |
| --- | ---: |
| Seen | 32343 |
| Truncated above 4096 tokens | 5145 |
| Left whole | 27198 |
| Estimated tokens in tool outputs before truncation | 59346599 |
| Estimated tokens in tool outputs after truncation | 40611366 |
| Orphan tool results skipped while windowing | 24 |

Sum of window token_count estimates: 58734680

## By repo (episodes / windows)

| Repo | Episodes | Windows |
| --- | ---: | ---: |
| chatterbuilt | 225 | 426 |
| conference-os | 804 | 1502 |
| the-gibson | 215 | 515 |

## By role (episodes / windows / tokens)

| Role | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| builder | 256 | 652 | 16836263 |
| reviewer | 886 | 1636 | 38650169 |
| other | 102 | 155 | 3248248 |

## Splits

Sample seed: 414
Train token cap: 16000000
Holdout fraction of builder PRs: 0.15
Holdout cutoff (earliest mergedAt kept out): 2026-09-29T03:37:12Z
Builder PRs: 86
Holdout PRs: 13
Holdout/train PR overlap: 0
Holdout/train episode overlap: 0

| Split | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| historical-v3, all roles | 1244 | 2443 | 58734680 |
| holdout-v3, builder, latest PRs | 34 | 77 | 1988302 |
| train pool, builder, not held out | 222 | 575 | 14847961 |
| train-v3, after sampling | 222 | 575 | 14847961 |
| builder pool left out by the cap | 0 | 0 | 0 |
| negatives-v3, builder, closed-unmerged | 19 | 53 | 1401862 |
| assessor-v3, reviewer with verdict | 509 | 901 | 20974245 |

### Train by repo

| Repo | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| chatterbuilt | 49 | 150 | 3954454 |
| conference-os | 67 | 158 | 3933740 |
| the-gibson | 106 | 267 | 6959767 |

### Holdout by repo

| Repo | Episodes | Windows | Tokens |
| --- | ---: | ---: | ---: |
| chatterbuilt | 9 | 18 | 506539 |
| conference-os | 9 | 24 | 613355 |
| the-gibson | 16 | 35 | 868408 |

## By vendor (episodes / windows)

| Vendor | Episodes | Windows |
| --- | ---: | ---: |
| claude | 23 | 28 |
| codex | 925 | 1795 |
| grok | 296 | 620 |

## Secret re-scan of the output file

Hits: 0

## Output validation

JSONL records: 2443
Bad JSON lines: 0
Schema error codes: {}

## Join method by role, repo, and vendor

| Join method | Role | Repo | Vendor | Episodes | Windows | Tokens |
| --- | --- | --- | --- | ---: | ---: | ---: |
| branch | builder | chatterbuilt | codex | 2 | 8 | 229736 |
| branch | builder | conference-os | codex | 6 | 16 | 455330 |
| branch | builder | the-gibson | codex | 3 | 15 | 412119 |
| branch | other | chatterbuilt | claude | 14 | 14 | 221821 |
| branch | other | chatterbuilt | codex | 2 | 3 | 58851 |
| branch | other | conference-os | codex | 4 | 6 | 114810 |
| branch | other | the-gibson | claude | 2 | 2 | 42352 |
| branch | other | the-gibson | codex | 9 | 10 | 170850 |
| branch | reviewer | chatterbuilt | codex | 72 | 107 | 2202667 |
| branch | reviewer | conference-os | codex | 574 | 1039 | 24686840 |
| branch | reviewer | the-gibson | codex | 24 | 38 | 845541 |
| commit | builder | chatterbuilt | claude | 1 | 2 | 34325 |
| commit | builder | chatterbuilt | codex | 2 | 4 | 77210 |
| commit | builder | chatterbuilt | grok | 44 | 123 | 3309383 |
| commit | builder | conference-os | grok | 40 | 87 | 2146534 |
| commit | builder | the-gibson | claude | 1 | 3 | 64247 |
| commit | builder | the-gibson | codex | 98 | 243 | 6333030 |
| commit | builder | the-gibson | grok | 15 | 40 | 1011811 |
| commit | other | chatterbuilt | codex | 3 | 8 | 192120 |
| commit | other | chatterbuilt | grok | 23 | 38 | 878661 |
| commit | other | conference-os | grok | 9 | 11 | 227151 |
| commit | other | the-gibson | claude | 4 | 6 | 128409 |
| commit | other | the-gibson | codex | 8 | 21 | 517911 |
| commit | other | the-gibson | grok | 4 | 7 | 147160 |
| commit | reviewer | chatterbuilt | codex | 11 | 13 | 346039 |
| commit | reviewer | chatterbuilt | grok | 6 | 11 | 267547 |
| commit | reviewer | conference-os | codex | 46 | 119 | 2968857 |
| commit | reviewer | conference-os | grok | 1 | 3 | 69052 |
| commit | reviewer | the-gibson | codex | 26 | 95 | 2477238 |
| issue-merged-unique | builder | conference-os | grok | 1 | 4 | 97475 |
| issue-merged-unique | builder | the-gibson | codex | 1 | 5 | 134338 |
| issue-merged-unique | builder | the-gibson | grok | 6 | 9 | 232108 |
| issue-merged-unique | other | the-gibson | claude | 1 | 1 | 5429 |
| issue-merged-unique | reviewer | chatterbuilt | codex | 1 | 1 | 31049 |
| issue-merged-unique | reviewer | conference-os | grok | 5 | 10 | 229714 |
| issue-merged-unique | reviewer | the-gibson | codex | 14 | 32 | 685016 |
| issue | builder | chatterbuilt | grok | 14 | 42 | 1092209 |
| issue | builder | conference-os | grok | 30 | 76 | 1873700 |
| issue | builder | the-gibson | codex | 1 | 2 | 52641 |
| issue | builder | the-gibson | grok | 10 | 26 | 681929 |
| issue | other | chatterbuilt | codex | 7 | 10 | 216632 |
| issue | other | chatterbuilt | grok | 8 | 10 | 161664 |
| issue | other | conference-os | grok | 4 | 8 | 164427 |
| issue | reviewer | chatterbuilt | codex | 4 | 4 | 16011 |
| issue | reviewer | chatterbuilt | grok | 16 | 39 | 929225 |
| issue | reviewer | conference-os | codex | 10 | 11 | 265974 |
| issue | reviewer | conference-os | grok | 75 | 113 | 2619512 |
| issue | reviewer | the-gibson | codex | 1 | 1 | 9887 |

## Unjoined sessions

| Join method | Sessions |
| --- | ---: |
| branch | 852 |
| commit | 343 |
| issue | 203 |
| issue-merged-unique | 29 |

| Unjoined reason | Sessions |
| --- | ---: |
| ambiguous_branch | 14 |
| ambiguous_commit | 669 |
| ambiguous_issue | 566 |
| no_match | 225 |
| no_signal | 98 |

## Notes

The user task is the issue title plus the first 1500 characters of the issue body.
Bodies are fetched with gh issue view and cached under ~/gibson-traces/cache/.
When the fetch fails, the user task stays the PR number, branch, and linked issue number.
The session's own user messages follow that task.
session_role is builder, reviewer, or other, from the tool calls the session made.
A builder wrote the repo (apply_patch, write, or edit) or ran git commit.
A reviewer ran under a read-only sandbox, or was a read-only session whose own query is a review.
Keyword evidence does not override a write or a commit.
The train split keeps every the-gibson and chatterbuilt builder episode that is not in the holdout,
then fills the token cap with conference-os builder episodes, seeded and round-robin by vendor.
The holdout is the latest fraction of builder PRs by mergedAt, recomputed on the builder set.
A pull request or episode in the holdout is not in the train split.
commit-merged-unique and issue-merged-unique mean several pull requests shared a commit or an issue
and exactly one of them was merged. Any other ambiguous session stays unjoined.
A session that still matches a secret pattern after redaction is dropped and counted.
The secret re-scan decodes each JSON line and checks the strings inside it.
A backslash added by JSON encoding is not itself a secret.
Provenance is the PR URL plus a hash of the session path. The raw path is not stored.
