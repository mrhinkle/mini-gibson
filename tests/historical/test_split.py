"""Train cap fill and the holdout disjoint rule. No network."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.historical.extract import (  # noqa: E402
    apply_splits,
    assert_holdout_disjoint,
    expand_holdout_by_issue,
    sample_training_episodes,
)


def _episode(key: str, repo: str, pr: int, day: int, tokens: int, vendor: str = "grok") -> dict:
    return {
        "key": key,
        "repo": repo,
        "pr": pr,
        "vendor": vendor,
        "role": "builder",
        "merged_at": f"2026-01-{day:02d}T00:00:00Z",
        "tokens": tokens,
        "windows": 1,
        "episode_id": f"{key}-w00",
    }


class SplitTests(unittest.TestCase):
    def test_non_conference_os_kept_then_conference_os_fills_the_cap(self):
        episodes = [
            {"repo": "the-gibson", "vendor": "grok", "tokens": 1000, "key": "g"},
            {"repo": "chatterbuilt", "vendor": "codex", "tokens": 1000, "key": "c"},
            {"repo": "conference-os", "vendor": "grok", "tokens": 800, "key": "o1"},
            {"repo": "conference-os", "vendor": "codex", "tokens": 800, "key": "o2"},
            {"repo": "conference-os", "vendor": "grok", "tokens": 5000, "key": "o3"},
        ]
        chosen = sample_training_episodes(episodes, cap=3000, seed=414)
        self.assertEqual([item["repo"] for item in chosen[:2]], ["the-gibson", "chatterbuilt"])
        self.assertEqual(sum(1 for item in chosen if item["repo"] == "conference-os"), 1)
        self.assertLessEqual(sum(item["tokens"] for item in chosen if item["repo"] == "conference-os") + 2000, 3000)
        over = sample_training_episodes(
            [
                {"repo": "the-gibson", "vendor": "grok", "tokens": 100, "key": "g"},
                {"repo": "conference-os", "vendor": "grok", "tokens": 50, "key": "o"},
            ],
            cap=40,
            seed=414,
        )
        self.assertEqual([item["repo"] for item in over], ["the-gibson"])

    def test_holdout_and_train_share_no_pr_or_episode(self):
        repos = ["the-gibson", "chatterbuilt", "conference-os"]
        metas = []
        records = []
        for index in range(12):
            meta = _episode(f"ep{index:02d}", repos[index % 3], 100 + index, index + 1, 100)
            metas.append(meta)
            records.append({"episode_id": meta["episode_id"], "repo": meta["repo"], "pr": meta["pr"]})
        stats: dict = {}
        train, hold = apply_splits(records, metas, stats, seed=414, cap=10_000, fraction=0.15)
        train_prs = {(row["repo"], row["pr"]) for row in train}
        hold_prs = {(row["repo"], row["pr"]) for row in hold}
        self.assertFalse(train_prs & hold_prs)
        train_ids = {row["episode_id"].rsplit("-w", 1)[0] for row in train}
        hold_ids = {row["episode_id"].rsplit("-w", 1)[0] for row in hold}
        self.assertFalse(train_ids & hold_ids)
        self.assertEqual(stats["holdout_prs"], 2)
        self.assertEqual(stats["overlap_prs"], 0)
        self.assertEqual(stats["overlap_episodes"], 0)
        self.assertIn("conference-os", {row["repo"] for row in train})
        self.assertIn("the-gibson", {row["repo"] for row in train})
        self.assertIn("chatterbuilt", {row["repo"] for row in train})

    def test_overlap_assertion_fires(self):
        shared = _episode("same", "the-gibson", 7, 2, 10)
        record = {"episode_id": "same-w00", "repo": "the-gibson", "pr": 7}
        with self.assertRaises(AssertionError):
            assert_holdout_disjoint([shared], [shared], [record], [record])

    def test_overlap_assertion_fires_on_shared_issue(self):
        held = _episode("late", "conference-os", 100, 20, 10)
        trained = _episode("early", "conference-os", 101, 1, 10)
        held["issues"] = [55]
        trained["issues"] = [55]
        hold_rec = {"episode_id": "late-w00", "repo": "conference-os", "pr": 100, "issue": 55}
        train_rec = {"episode_id": "early-w00", "repo": "conference-os", "pr": 101, "issue": 55}
        with self.assertRaises(AssertionError):
            assert_holdout_disjoint([trained], [held], [train_rec], [hold_rec])

    def test_shared_issue_with_a_held_out_pr_is_not_in_train(self):
        """PR 100 closes issue 55 and is the latest PR. PR 101 closes the same issue and must not train."""
        metas = [
            _episode("late", "conference-os", 100, 20, 10),
            _episode("early", "conference-os", 101, 1, 10),
            _episode("other", "the-gibson", 7, 10, 10),
        ]
        metas[0]["issues"] = [55]
        metas[1]["issues"] = [55]
        metas[2]["issues"] = [7]
        records = [
            {
                "episode_id": meta["episode_id"],
                "repo": meta["repo"],
                "pr": meta["pr"],
                "issue": meta["issues"][0],
            }
            for meta in metas
        ]
        dated = {("conference-os", 100)}
        full, extra = expand_holdout_by_issue(dated, metas)
        self.assertIn(("conference-os", 101), full)
        self.assertEqual(extra, {("conference-os", 101)})
        stats: dict = {}
        train, hold = apply_splits(records, metas, stats, seed=414, cap=10_000, fraction=0.15)
        train_prs = {row["pr"] for row in train}
        hold_prs = {row["pr"] for row in hold}
        self.assertIn(100, hold_prs)
        self.assertIn(101, hold_prs)
        self.assertNotIn(101, train_prs)
        self.assertNotIn(100, train_prs)
        self.assertIn(7, train_prs)
        self.assertEqual(stats["overlap_issues"], 0)
        self.assertGreaterEqual(stats["holdout_lineage_prs"], 1)
        self.assertEqual(stats["holdout_cutoff"], "2026-01-20T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
