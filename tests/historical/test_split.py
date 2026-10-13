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


if __name__ == "__main__":
    unittest.main()
