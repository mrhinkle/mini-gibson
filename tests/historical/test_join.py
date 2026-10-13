"""Join methods (b) commit SHA and (c) issue number. No network."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.historical.join import (  # noqa: E402
    PrCatalog,
    collect_signals,
    commit_shas_from_events,
    commit_shas_from_tool_output,
    decide_join,
    edit_coverage,
    header_join_keys,
    header_target,
    issue_numbers_from_path,
    issue_numbers_from_prompt,
    issues_for_join,
    jaccard,
    parse_prompt_declaration,
    prompt_join_keys,
    resolve_overlap,
    successful_edit_files,
    usable_commit_shas,
)

FX = Path(__file__).resolve().parent / "fixtures"


def _catalog() -> PrCatalog:
    return PrCatalog({
        "conference-os": [
            {
                "number": 9,
                "state": "MERGED",
                "headRefName": "feat/gate",
                "closingIssuesReferences": [
                    {"number": 55, "repository": {"name": "conference-os"}},
                ],
            },
            {
                "number": 12,
                "state": "MERGED",
                "headRefName": "feat/other",
                "closingIssuesReferences": [
                    {"number": 2095, "repository": {"name": "conference-os"}},
                ],
            },
            {
                "number": 13,
                "state": "CLOSED",
                "headRefName": "feat/other-closed",
                "closingIssuesReferences": [
                    {"number": 2095, "repository": {"name": "conference-os"}},
                ],
            },
            {
                "number": 40,
                "state": "MERGED",
                "headRefName": "feat/shared",
                "closingIssuesReferences": [],
            },
            {
                "number": 41,
                "state": "CLOSED",
                "headRefName": "feat/shared",
                "closingIssuesReferences": [],
            },
        ],
        "chatterbuilt": [],
        "the-gibson": [
            {
                "number": 70,
                "state": "MERGED",
                "headRefName": "feat/gibson",
                "closingIssuesReferences": [
                    {"number": 414, "repository": {"name": "the-gibson"}},
                ],
            },
        ],
    })


class JoinMethodTests(unittest.TestCase):
    def test_path_and_prompt_issue_numbers(self):
        self.assertEqual(issue_numbers_from_path("/Users/x/Code/conference-os-wt/lane-2095"), [2095])
        self.assertEqual(issue_numbers_from_path("/Users/x/Code/cos-2084-mcp-legal"), [2084])
        self.assertEqual(issue_numbers_from_path("/Users/x/Code/wt-364-linkedin"), [364])
        self.assertEqual(issue_numbers_from_path("/Users/x/Code/cb-lane-605"), [605])
        self.assertEqual(issue_numbers_from_prompt("rules #1\n<user_query>\nissue #2095 and #12\n</user_query>"), [2095, 12])
        # A single worktree issue wins over other hashes in the prompt.
        self.assertEqual(issues_for_join("/tmp/lane-2095", "also see #12 and issue #88"), [2095])

    def test_method_b_commit_sha_beats_issue(self):
        signals = collect_signals(FX / "join_method_b.jsonl", "grok", "/tmp/lane-55")
        self.assertEqual(signals["shas"], ["deadbeef1", "aaaabbbbccccddddeeeeffff0000111122223333"])
        self.assertEqual(signals["issues"], [55])
        catalog = _catalog()
        # deadbeef1 is the session's commit. The bare SHA is not in any PR.
        commit_keys = [("conference-os", 9)]
        decision = decide_join(
            [],
            commit_keys,
            catalog.issue_keys("conference-os", signals["issues"]),
            commit_attempted=True,
            issue_attempted=True,
        )
        self.assertEqual(decision["join_method"], "commit")
        self.assertEqual(decision["pr"], 9)

    def test_method_b_two_prs_does_not_fall_through(self):
        decision = decide_join(
            [],
            [("conference-os", 9), ("conference-os", 12)],
            [("conference-os", 12)],
            commit_attempted=True,
            issue_attempted=True,
        )
        self.assertEqual(decision["join_method"], "")
        self.assertEqual(decision["reason"], "ambiguous_commit")

    def test_method_c_issue_from_fixture_prompt_and_path(self):
        signals = collect_signals(
            FX / "join_method_c.jsonl",
            "grok",
            "/Users/x/Code/conference-os-wt/lane-2095",
        )
        self.assertEqual(signals["shas"], [])
        self.assertEqual(signals["issues"], [2095])
        self.assertEqual(signals["prompt_repo"], "conference-os")
        self.assertNotIn(999, signals["issues"])
        catalog = _catalog()
        # Two PRs close 2095, so the fixture path is ambiguous until the catalog has one.
        ambiguous = decide_join(
            [],
            [],
            catalog.issue_keys("conference-os", signals["issues"]),
            commit_attempted=False,
            issue_attempted=True,
        )
        self.assertEqual(ambiguous["reason"], "ambiguous_issue")
        only = [key for key in catalog.issue_keys("conference-os", [2095]) if key[1] == 12]
        decision = decide_join([], [], only, commit_attempted=False, issue_attempted=True)
        self.assertEqual(decision["join_method"], "issue")
        self.assertEqual((decision["repo"], decision["pr"]), ("conference-os", 12))

    def test_method_c_worktree_without_repo_name(self):
        catalog = _catalog()
        keys = catalog.issue_keys("", [414])
        decision = decide_join([], [], keys, commit_attempted=False, issue_attempted=True)
        self.assertEqual(decision["join_method"], "issue")
        self.assertEqual((decision["repo"], decision["pr"]), ("the-gibson", 70))

    def test_branch_wins_and_shared_branch_is_ambiguous(self):
        catalog = _catalog()
        unique = decide_join(
            catalog.branch_keys("conference-os", "feat/gate"),
            [("conference-os", 12)],
            [("conference-os", 12)],
            commit_attempted=True,
            issue_attempted=True,
        )
        self.assertEqual(unique["join_method"], "branch")
        self.assertEqual(unique["pr"], 9)
        shared = decide_join(
            catalog.branch_keys("conference-os", "feat/shared"),
            [("conference-os", 9)],
            [],
            commit_attempted=True,
            issue_attempted=False,
        )
        self.assertEqual(shared["reason"], "ambiguous_branch")

    def test_ambiguous_commit_resolves_when_one_pr_merged(self):
        states = {
            ("conference-os", 9): "MERGED",
            ("conference-os", 13): "CLOSED",
            ("conference-os", 12): "MERGED",
        }
        resolved = decide_join(
            [],
            [("conference-os", 9), ("conference-os", 13)],
            [("conference-os", 12)],
            commit_attempted=True,
            issue_attempted=True,
            pr_states=states,
        )
        self.assertEqual(resolved["join_method"], "commit-merged-unique")
        self.assertEqual((resolved["repo"], resolved["pr"]), ("conference-os", 9))
        both_merged = decide_join(
            [],
            [("conference-os", 9), ("conference-os", 12)],
            [("conference-os", 12)],
            commit_attempted=True,
            issue_attempted=True,
            pr_states={("conference-os", 9): "MERGED", ("conference-os", 12): "MERGED"},
        )
        self.assertEqual(both_merged["reason"], "ambiguous_commit")
        none_merged = decide_join(
            [],
            [("conference-os", 13), ("conference-os", 41)],
            [],
            commit_attempted=True,
            issue_attempted=False,
            pr_states={("conference-os", 13): "CLOSED", ("conference-os", 41): "CLOSED"},
        )
        self.assertEqual(none_merged["reason"], "ambiguous_commit")

    def test_ambiguous_issue_resolves_when_one_pr_merged(self):
        catalog = _catalog()
        states = {key: (pr.get("state") or "") for key, pr in catalog.by_key.items()}
        resolved = decide_join(
            [],
            [],
            catalog.issue_keys("conference-os", [2095]),
            commit_attempted=False,
            issue_attempted=True,
            pr_states=states,
        )
        self.assertEqual(resolved["join_method"], "issue-merged-unique")
        self.assertEqual((resolved["repo"], resolved["pr"]), ("conference-os", 12))
        still = decide_join(
            [],
            [],
            [("the-gibson", 70), ("conference-os", 9)],
            commit_attempted=False,
            issue_attempted=True,
            pr_states={("the-gibson", 70): "MERGED", ("conference-os", 9): "MERGED"},
        )
        self.assertEqual(still["reason"], "ambiguous_issue")

    def test_tool_output_ignores_git_log_lines(self):
        text = "abc1234 Fix something old\n[feat/gate deadbeef1] Fix the gate\n"
        self.assertEqual(commit_shas_from_tool_output(text), ["deadbeef1"])

    def test_unrelated_rev_parse_is_not_a_created_sha(self):
        full = "aaaabbbbccccddddeeeeffff0000111122223333"
        other = "ffffffffffffffffffffffffffffffffffffffff"
        shown = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        logged = "1111111111111111111111111111111111111111"
        displayed = "f8f8f15b1939e73d4cb18e7ad824211e895fc853"
        events = [
            ("git commit -m x", "[feat/gate deadbeef1] Fix the gate\n"),
            ("git rev-parse HEAD", full + "\n"),
            ("git rev-parse origin/main", other + "\n"),
            ("git show --stat " + other, "commit " + shown + "\n"),
            ("git log -1 --format=%H", logged + "\n"),
            (
                "git rev-parse --abbrev-ref HEAD && git merge-base HEAD origin/main",
                displayed + "\n",
            ),
        ]
        created = ["deadbeef1", full]
        self.assertEqual(commit_shas_from_events(events), created)
        self.assertEqual(usable_commit_shas(events), created)
        self.assertEqual(
            commit_shas_from_events([("git rev-parse HEAD", full + "\n")]),
            [],
        )
        self.assertEqual(usable_commit_shas(events, {other}), created + [other])
        self.assertNotIn(displayed, usable_commit_shas(events, {other}))
        self.assertNotIn(logged, usable_commit_shas(events))

    def test_prompt_pr_ignores_later_tool_output(self):
        catalog = PrCatalog({
            "conference-os": [
                {
                    "number": 618,
                    "state": "MERGED",
                    "headRefName": "lane/618",
                    "closingIssuesReferences": [],
                },
                {
                    "number": 12,
                    "state": "MERGED",
                    "headRefName": "feat/other",
                    "closingIssuesReferences": [],
                },
            ],
            "chatterbuilt": [],
            "the-gibson": [],
        })
        lines = [
            {"type": "system", "content": "You are a coder. Do not treat system text as the task."},
            {
                "type": "user",
                "content": "<user_query>TASK The-AIE/conference-os PR #618. Work in the lane.</user_query>",
            },
            {"type": "assistant", "content": "Checking the other pull request."},
            {"type": "tool_result", "content": "gh pr view 12\nThe-AIE/conference-os#12 is unrelated."},
            {"type": "user", "content": "<user_query>Also see PR #12.</user_query>"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in lines), encoding="utf-8")
            signals = collect_signals(path, "grok", "/tmp/lane-618")
        declaration = signals["declaration"]
        self.assertEqual(declaration["prs"], [("conference-os", 618)])
        self.assertNotIn(12, [number for _, number in declaration["prs"]])
        _branch_keys, pr_keys = prompt_join_keys(declaration, catalog)
        decision = decide_join(
            [],
            [],
            [],
            commit_attempted=False,
            issue_attempted=False,
            prompt_pr_keys=pr_keys,
            prompt_pr_attempted=bool(pr_keys),
        )
        self.assertEqual(decision["join_method"], "prompt-pr")
        self.assertEqual(decision["pr"], 618)

    def test_prompt_branch_prefers_your_branch(self):
        text = (
            "TASK The-AIE/conference-os issue #2235, "
            "integration branch `chore/oss-cleanup`, your branch `lane/oss-c1`."
        )
        declaration = parse_prompt_declaration(text)
        self.assertEqual(declaration["branch"], "lane/oss-c1")
        self.assertEqual(declaration["repo"], "conference-os")
        self.assertEqual(declaration["prs"], [])

    def test_overlap_margin(self):
        session = {f"s{i}" for i in range(5)}
        high = {f"s{i}" for i in range(4)}
        low = {"s0", "a", "b", "c", "d", "e"}
        self.assertAlmostEqual(jaccard(session, high), 0.8)
        self.assertAlmostEqual(jaccard(session, low), 0.1)
        clear = {
            "join_method": "",
            "reason": "ambiguous_issue",
            "repo": "",
            "pr": "",
            "candidates": [("conference-os", 1), ("conference-os", 2)],
        }

        def files_for(key):
            return high if key[1] == 1 else low

        picked = resolve_overlap(clear, session, files_for, role="builder")
        self.assertEqual(picked["join_method"], "coverage")
        self.assertEqual(picked["pr"], 1)

        close_session = {f"f{i}" for i in range(10)}
        first = {f"f{i}" for i in range(6)}
        second = {f"f{i}" for i in range(5)}
        self.assertAlmostEqual(jaccard(close_session, first), 0.6)
        self.assertAlmostEqual(jaccard(close_session, second), 0.5)
        close = {
            "join_method": "",
            "reason": "ambiguous_prompt",
            "repo": "",
            "pr": "",
            "candidates": [("the-gibson", 8), ("the-gibson", 9)],
        }

        def close_files(key):
            return first if key[1] == 8 else second

        stayed = resolve_overlap(close, close_session, close_files, role="builder")
        self.assertEqual(stayed["join_method"], "")
        self.assertEqual(stayed["reason"], "ambiguous_prompt")

    def test_builder_zero_overlap_is_rejected(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "e1",
                    "function": {
                        "name": "edit_file",
                        "arguments": json.dumps({"file_path": "/tmp/lane/src/ok.py"}),
                    },
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "e1",
                "content": "The file /tmp/lane/src/ok.py has been updated successfully.",
            },
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "e2",
                    "function": {
                        "name": "edit_file",
                        "arguments": json.dumps({"file_path": "/tmp/lane/src/bad.py"}),
                    },
                }],
            },
            {"role": "tool", "tool_call_id": "e2", "content": "string to replace not found"},
        ]
        edited = successful_edit_files(messages, ["/tmp/lane"])
        self.assertEqual(edited, ["src/ok.py"])
        decision = {
            "join_method": "prompt-pr",
            "reason": "",
            "repo": "conference-os",
            "pr": 618,
            "candidates": [],
        }
        rejected = resolve_overlap(
            decision,
            edited,
            lambda key: {"other.py"},
            role="builder",
        )
        self.assertEqual(rejected["join_method"], "")
        self.assertEqual(rejected["reason"], "no_file_overlap")
        kept = resolve_overlap(decision, edited, lambda key: {"src/ok.py"}, role="builder")
        self.assertEqual(kept["join_method"], "prompt-pr")
        # A fleet PR is the union of every session. Two of thirty files is
        # Jaccard ~0.07 and coverage 1. Both edits are on the PR, so it stays.
        wide = {"src/ok.py", "src/other.py", *(f"extra{i}.py" for i in range(28))}
        subset = resolve_overlap(decision, edited, lambda key: wide, role="builder")
        self.assertEqual(subset["join_method"], "prompt-pr")
        self.assertAlmostEqual(edit_coverage(set(edited), wide), 1.0)
        self.assertLess(jaccard(set(edited), wide), 0.3)
        # Most of the session's edits are absent from the PR.
        stray = {f"f{i}.py" for i in range(10)}
        weak = resolve_overlap(decision, stray, lambda key: {"f0.py", "f1.py"}, role="builder")
        self.assertEqual(weak["reason"], "no_file_overlap")
        reviewer = resolve_overlap(decision, set(), lambda key: {"other.py"}, role="reviewer")
        self.assertEqual(reviewer["join_method"], "prompt-pr")

    def _header_catalog(self) -> PrCatalog:
        return PrCatalog({
            "conference-os": [
                {"number": 618, "state": "MERGED", "headRefName": "lane/618", "closingIssuesReferences": []},
                {"number": 600, "state": "MERGED", "headRefName": "lane/600", "closingIssuesReferences": []},
                {"number": 612, "state": "MERGED", "headRefName": "lane/612", "closingIssuesReferences": []},
                {
                    "number": 9,
                    "state": "MERGED",
                    "headRefName": "feat/gate",
                    "closingIssuesReferences": [
                        {"number": 55, "repository": {"name": "conference-os"}},
                    ],
                },
            ],
            "chatterbuilt": [],
            "the-gibson": [],
        })

    def _decide_prompt(self, text: str, catalog: PrCatalog) -> dict:
        declaration = parse_prompt_declaration(text)
        header = header_target(text)
        branch_keys, pr_keys = prompt_join_keys(declaration, catalog, "conference-os")
        return decide_join(
            [],
            [],
            [],
            commit_attempted=False,
            issue_attempted=False,
            prompt_branch_keys=branch_keys,
            prompt_pr_keys=pr_keys,
            prompt_branch_attempted=bool(branch_keys),
            prompt_pr_attempted=bool(pr_keys),
            header_keys=header_join_keys(header, catalog, "conference-os"),
            header_declared=bool(header.get("kind")),
        )

    def test_header_pr_beats_later_numbers(self):
        text = (
            "TASK (Grok, headless coder) — The-AIE/conference-os PR #618, "
            "worktree `/tmp/lane-618`.\n"
            "Prior art is PR #600 and PR #612. Do not enter lane-55.\n"
        )
        header = header_target(text)
        self.assertEqual(header["kind"], "pr")
        self.assertEqual(header["pr"], 618)
        decision = self._decide_prompt(text, self._header_catalog())
        self.assertEqual(decision["join_method"], "prompt-header")
        self.assertEqual(decision["pr"], 618)
        # A header PR the catalog does not have does not fall through to the body.
        missing = (
            "TASK (Grok, headless coder) — The-AIE/conference-os PR #999.\n"
            "Context mentions PR #618 and PR #600.\n"
        )
        missed = self._decide_prompt(missing, self._header_catalog())
        self.assertEqual(missed["join_method"], "")
        self.assertNotEqual(missed.get("pr"), 618)
        # "PR #370 and #371" is two numbers. It is not a header PR.
        pair = "Validate metadata for PR #370 and #371.\n"
        self.assertEqual(header_target(pair)["kind"], "")

    def test_header_branch_only_joins_that_branch(self):
        text = (
            "LENS: the body is not the header.\n"
            "TASK (Grok, headless coder) — The-AIE/conference-os branch `feat/gate`, "
            "worktree `/tmp/wt`.\n"
            "Prior art is PR #600 and PR #612. your branch `lane/600` is the old attempt.\n"
        )
        header = header_target(text)
        self.assertEqual(header["kind"], "branch")
        self.assertEqual(header["branch"], "feat/gate")
        decision = self._decide_prompt(text, self._header_catalog())
        self.assertEqual(decision["join_method"], "prompt-header")
        self.assertEqual(decision["repo"], "conference-os")
        self.assertEqual(decision["pr"], 9)
        # A branch on the header beats a PR number on that same line.
        both = (
            "TASK (Grok, headless coder) — The-AIE/conference-os branch `feat/gate`, PR #600.\n"
            "Body mentions PR #612.\n"
        )
        branched = self._decide_prompt(both, self._header_catalog())
        self.assertEqual(branched["pr"], 9)
        # A branch the catalog does not have uses the header PR, not the body.
        missed_branch = (
            "TASK (Grok, headless coder) — The-AIE/conference-os branch `lane/missing`, PR #618.\n"
            "Body mentions PR #600 and PR #612.\n"
        )
        fallback = self._decide_prompt(missed_branch, self._header_catalog())
        self.assertEqual(fallback["join_method"], "prompt-header")
        self.assertEqual(fallback["pr"], 618)

    def test_coverage_margin_not_jaccard(self):
        session = {f"f{i}.py" for i in range(10)}
        wide = set(session) | {f"extra{i}.py" for i in range(20)}
        partial = {f"f{i}.py" for i in range(4)}
        self.assertAlmostEqual(edit_coverage(session, wide), 1.0)
        self.assertAlmostEqual(edit_coverage(session, partial), 0.4)
        self.assertLess(jaccard(session, wide), 0.5)
        clear = {
            "join_method": "",
            "reason": "ambiguous_prompt",
            "repo": "",
            "pr": "",
            "candidates": [("conference-os", 618), ("conference-os", 600)],
        }

        def files_for(key):
            return wide if key[1] == 618 else partial

        picked = resolve_overlap(clear, session, files_for, role="builder")
        self.assertEqual(picked["join_method"], "coverage")
        self.assertEqual(picked["pr"], 618)

        close = {
            "join_method": "",
            "reason": "ambiguous_prompt",
            "repo": "",
            "pr": "",
            "candidates": [("conference-os", 1), ("conference-os", 2)],
        }
        six = {f"f{i}.py" for i in range(6)}
        five = {f"f{i}.py" for i in range(5)}
        self.assertAlmostEqual(edit_coverage(session, six), 0.6)
        self.assertAlmostEqual(edit_coverage(session, five), 0.5)

        def close_files(key):
            return six if key[1] == 1 else five

        stayed = resolve_overlap(close, session, close_files, role="builder")
        self.assertEqual(stayed["join_method"], "")
        self.assertEqual(stayed["reason"], "ambiguous_prompt")

        tied = resolve_overlap(
            clear,
            session,
            lambda key: set(session),
            role="builder",
            header_numbers={618},
        )
        self.assertEqual(tied["join_method"], "coverage")
        self.assertEqual(tied["pr"], 618)
        still = resolve_overlap(
            clear,
            session,
            lambda key: set(session),
            role="builder",
            header_numbers={618, 600},
        )
        self.assertEqual(still["reason"], "ambiguous_prompt")

    def test_reviewer_does_not_become_builder(self):
        from training.historical.extract import classify_session_role

        messages = [
            {
                "role": "user",
                "content": (
                    "<user_query>Perform a bounded read-only review.\n"
                    "TASK (Grok) — The-AIE/conference-os PR #618.\n"
                    "Also mentioned: PR #600 and PR #612.\n"
                    "</user_query>"
                ),
            },
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "e1",
                    "function": {
                        "name": "edit_file",
                        "arguments": json.dumps({"file_path": "/tmp/lane/src/ok.py"}),
                    },
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "e1",
                "content": "The file /tmp/lane/src/ok.py has been updated successfully.",
            },
        ]
        self.assertEqual(classify_session_role(messages, "read-only"), "reviewer")
        edited = successful_edit_files(messages, ["/tmp/lane"])
        ambiguous = {
            "join_method": "",
            "reason": "ambiguous_prompt",
            "repo": "",
            "pr": "",
            "candidates": [("conference-os", 618), ("conference-os", 600)],
        }

        def files_for(key):
            if key[1] == 618:
                return {"src/ok.py", *(f"extra{i}.py" for i in range(20))}
            return {"other.py"}

        picked = resolve_overlap(ambiguous, edited, files_for, role="reviewer")
        self.assertEqual(picked["join_method"], "coverage")
        self.assertEqual(picked["pr"], 618)
        self.assertEqual(classify_session_role(messages, "read-only"), "reviewer")
        self.assertNotIn("role", picked)
        header = {
            "join_method": "prompt-header",
            "reason": "",
            "repo": "conference-os",
            "pr": 618,
            "candidates": [],
        }
        kept = resolve_overlap(header, edited, files_for, role="reviewer")
        self.assertEqual(kept["join_method"], "prompt-header")
        self.assertEqual(classify_session_role(messages, "read-only"), "reviewer")


if __name__ == "__main__":
    unittest.main()
