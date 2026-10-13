"""Join methods (b) commit SHA and (c) issue number. No network."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.historical.join import (  # noqa: E402
    PrCatalog,
    collect_signals,
    commit_shas_from_tool_output,
    decide_join,
    issue_numbers_from_path,
    issue_numbers_from_prompt,
    issues_for_join,
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


if __name__ == "__main__":
    unittest.main()
