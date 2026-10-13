"""Redaction drops secret material and the gate drops anything left over."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.historical.extract import parse_session  # noqa: E402
from training.historical.redact import (  # noqa: E402
    command_lists_home,
    drop_if_residual,
    redact_record,
    redact_text,
    residual_json_text,
    residual_names,
)

FX = Path(__file__).resolve().parent / "fixtures"
SECRETS = (
    "sk-FAKEFAKEFAKEFAKEFAKE",
    "op://Private/Fake/field",
    "fakefakefakefake12",
    "/Users/mrhinkle",
    "ada@example.com",
    "BEGIN OPENSSH PRIVATE KEY",
    "supersecretvalue",
    "ghp_FAKEFAKEFAKEFAKEFAKEFAKE",
    "user:password",
    "MacBook-Pro-4",
)


class RedactTests(unittest.TestCase):
    def test_synthetic_fixture_secrets_are_removed(self):
        messages = parse_session(FX / "secrets.claude.jsonl", "claude")
        raw = json.dumps(messages)
        self.assertIn("sk-FAKEFAKEFAKEFAKEFAKE", raw)
        record = {
            "episode_id": "e",
            "repo": "the-gibson",
            "task": "PR the-gibson#1 on branch feat/x",
            "messages": messages,
            "outcome": "merged",
            "provenance": ["https://github.com/The-AIE/the-gibson/pull/1", "session:0123456789abcdef"],
        }
        cleaned, hits = redact_record(record)
        self.assertEqual(hits, [])
        blob = json.dumps(cleaned)
        for secret in SECRETS:
            self.assertNotIn(secret, blob)
        self.assertIn("<redacted", blob)
        self.assertIn("<email>", blob)
        self.assertIn("/Users/<user>", blob)
        self.assertIn("<host>", blob)
        again, hits2 = redact_record(cleaned)
        self.assertEqual(hits2, [])
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(cleaned, sort_keys=True))
        kept, residual = drop_if_residual(cleaned)
        self.assertIsNotNone(kept)
        self.assertEqual(residual, [])

    def test_residual_record_is_dropped(self):
        poisoned = {"messages": [{"role": "tool", "content": "token sk-FAKEFAKEFAKEFAKEFAKE"}]}
        self.assertTrue(residual_names(json.dumps(poisoned)))
        kept, hits = drop_if_residual(poisoned)
        self.assertIsNone(kept)
        self.assertIn("api_key", hits)
        # The gate reports the pattern name, not the matched value.
        self.assertNotIn("sk-FAKE", " ".join(hits))

    def test_dotenv_contents_are_replaced(self):
        record = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "e1",
                        "type": "function",
                        "function": {"name": "run_command", "arguments": json.dumps({"command": "cat .env"})},
                    }],
                },
                {"role": "tool", "tool_call_id": "e1", "content": "API_TOKEN=abcdef\nPLAIN=value\n"},
            ]
        }
        cleaned, hits = redact_record(record)
        self.assertEqual(hits, [])
        self.assertEqual(cleaned["messages"][1]["content"], "[.env contents redacted]")
        self.assertNotIn("abcdef", json.dumps(cleaned))

    def test_json_escapes_are_not_residual_secrets(self):
        bare = {"messages": [{"role": "tool", "content": '{"url": "postgres://"}'}]}
        ellipsis = {"messages": [{"role": "tool", "content": "OPENAI_API_KEY=...\\n"}]}
        at_file = {"messages": [{"role": "tool", "content": 'file.tsx">\n@global.ts\n</Widget'}]}
        for record in (bare, ellipsis, at_file):
            cleaned, hits = redact_record(record)
            self.assertEqual(hits, [])
            self.assertEqual(residual_json_text(json.dumps(cleaned)), [])
        self.assertEqual(residual_names(json.dumps(bare)), ["connection_string"])

    def test_connection_string_split_by_newline_is_redacted(self):
        record = {"messages": [{"role": "tool", "content": "postgres://user:s3cret-value@localhost/db"}]}
        split = {"messages": [{"role": "tool", "content": "postgres://\nuser:s3cret-value@localhost/db"}]}
        for record in (record, split):
            cleaned, hits = redact_record(record)
            self.assertEqual(hits, [])
            self.assertNotIn("s3cret-value", json.dumps(cleaned))
            self.assertIn("<redacted>", json.dumps(cleaned))

    def test_truncated_secret_prefix_is_dropped(self):
        """Eight or more characters of a known secret shape is residual, even when the token was cut."""
        samples = (
            "ghp_FAKEFA",
            "github_pat_short",
            "AKIA1234ABCD",
            "Bearer abcdefgh",
            "sk-ant-abcdef",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertGreaterEqual(len(sample.replace("Bearer ", "")), 8)
                self.assertTrue(residual_names(sample), sample)
                kept, hits = drop_if_residual({"messages": [{"role": "tool", "content": sample}]})
                self.assertIsNone(kept)
                self.assertTrue(hits)
                cleaned, redacted_hits = redact_record({"messages": [{"role": "tool", "content": sample}]})
                self.assertEqual(redacted_hits, [])
                blob = json.dumps(cleaned)
                self.assertNotIn("ghp_", blob)
                self.assertNotIn("github_pat_", blob)
                self.assertNotIn("AKIA", blob)
                self.assertNotIn("sk-ant-", blob)
                self.assertNotRegex(blob, r"Bearer\s+[A-Za-z0-9]{8,}")
        real = {"messages": [{"role": "tool", "content": "OPENAI_API_KEY=supersecretvalue"}]}
        cleaned, real_hits = redact_record(real)
        self.assertEqual(real_hits, [])
        self.assertNotIn("supersecretvalue", json.dumps(cleaned))

    def test_secret_split_across_messages_is_redacted(self):
        """A secret, email, or bearer token broken across two strings is one match on the join."""
        ghp_body = "FAKEFAKEFAKEFAKEFAKEFAKE"
        cases = (
            ("ghp_", ghp_body, "ghp_"),
            ("see alice@", "example.com later", "example.com"),
            ("use Bearer ", "abcdefghijklmnopqrstuvwxyz now", "abcdefghijklmnopqrstuvwxyz"),
        )
        for left, right, leaked in cases:
            with self.subTest(leaked=leaked[:12]):
                record = {
                    "messages": [
                        {"role": "assistant", "content": left},
                        {"role": "tool", "tool_call_id": "t", "content": right},
                    ]
                }
                raw_join = left + right
                self.assertTrue(residual_names(raw_join))
                poisoned, poison_hits = drop_if_residual(record)
                self.assertIsNone(poisoned)
                self.assertTrue(poison_hits)
                cleaned, hits = redact_record(record)
                self.assertEqual(hits, [])
                joined = "".join(message["content"] for message in cleaned["messages"])
                self.assertNotIn(leaked, joined)
                self.assertEqual(residual_names(joined), [])
                self.assertEqual(residual_json_text(json.dumps(cleaned)), [])
                if leaked == "example.com":
                    self.assertIn("<email>", joined)
                    self.assertIn("later", cleaned["messages"][1]["content"])
                if leaked == ghp_body:
                    self.assertIn("<redacted-key>", joined)
                    self.assertNotIn(ghp_body, joined)

    def test_redact_text_is_idempotent(self):
        sample = "mail ada@example.com host MacBook-Pro-4 path /Users/mrhinkle/Code Bearer fakefakefakefake12"
        once = redact_text(sample)
        self.assertEqual(redact_text(once), once)
        self.assertEqual(residual_names(once), [])

    def test_signed_off_by_email_and_username_shapes(self):
        """The shapes that survived round 1: a Signed-off-by address, an escaped dot, and user@<host>."""
        shapes = [
            "Signed-off-by: Mark Hinkle <mrhinkle@example.com>",
            "rg -q '^Signed-off-by: Mark Hinkle <mrhinkle@example\\.com>$'",
            "Session: mrhinkle@<host>",
            "Session: mrhinkle@MacBook-Pro-4",
            "login markhinkle and repo mrhinkle/conference-os",
            "pattern 'ghp_' and PRIVATE KEY and |sk-(?:ant-)?",
            "keep task-name risk-level ask-user disk-image mask-bit",
        ]
        email = __import__("re").compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        for sample in shapes:
            with self.subTest(sample=sample[:48]):
                cleaned = redact_text(sample)
                self.assertNotIn("mrhinkle", cleaned.lower())
                self.assertNotIn("markhinkle", cleaned.lower())
                self.assertNotIn("ghp_", cleaned)
                self.assertNotIn("PRIVATE KEY", cleaned)
                self.assertIsNone(email.search(cleaned))
                self.assertEqual(residual_names(cleaned), [])
                self.assertEqual(redact_text(cleaned), cleaned)
        kept = redact_text(shapes[-1])
        self.assertIn("task-name", kept)
        self.assertIn("risk-level", kept)
        self.assertIn("ask-user", kept)

    def test_username_is_a_substring_and_session_paths_collapse(self):
        """Shapes the word-boundary scan kept: tokens, encoded paths, bare /Users/."""
        samples = {
            "/tmp/claude-501/-Users-mrhinkle-Claude-Cowork/cbed6935-e2c1-4eb9-822f-657ac9a42641": "<abs>/\u2026",
            "/private/tmp/claude-501/-Users-markhinkle-Claude-Cowork/abc/scratchpad/hero.png": "<abs>/\u2026",
            "unsigned, and mrhinkle-authored agent commits": "<user>-authored",
            "neuro-mancer-broker-mrhinkle": "neuro-mancer-broker-<user>",
            "mrhinkle_cnsvs-network/\nmrhinkle_cortex/": "<user>_cnsvs-network/",
            "if grep -E -n '/Users/' \"$LIVE\"": "/Users/<user>",
            "also /home/ and MARKHINKLE": "/home/<user>",
        }
        for sample, expect in samples.items():
            with self.subTest(sample=sample[:48]):
                before = residual_names(sample)
                if "mrhinkle" in sample.lower() or "markhinkle" in sample.lower():
                    self.assertIn("username", before)
                if "/Users/" in sample or "/home/" in sample:
                    self.assertIn("home_path", before)
                cleaned = redact_text(sample)
                self.assertIn(expect, cleaned)
                self.assertNotIn("mrhinkle", cleaned.lower())
                self.assertNotIn("markhinkle", cleaned.lower())
                self.assertNotRegex(cleaned, r"/Users/(?!<user>)")
                self.assertNotRegex(cleaned, r"/home/(?!<user>)")
                self.assertEqual(residual_names(cleaned), [])
                self.assertEqual(redact_text(cleaned), cleaned)
        encoded = json.dumps({"content": "broker-mrhinkle and /tmp/claude-501/-Users-mrhinkle-x/u"})
        self.assertIn("username", residual_json_text(encoded))
        cleaned = redact_text(json.loads(encoded)["content"])
        self.assertEqual(residual_json_text(json.dumps({"content": cleaned})), [])

    def test_home_directory_listings_are_removed(self):
        listing = "mrhinkle_cnsvs-network/\nmrhinkle_cortex/\nCode/\n"
        cases = [
            ("ls -la ~", True),
            ("find ~ -maxdepth 2 -type d", True),
            ("find /Users/mrhinkle -maxdepth 3 -type d -name the-gibson", True),
            ('find "$HOME" -maxdepth 1', True),
            ("ls ~/Code/proj", False),
            ("find /Users/mrhinkle/Code -maxdepth 2 -type d", False),
            ("find . -maxdepth 2 -type d", False),
        ]
        for command, drop in cases:
            with self.subTest(command=command):
                self.assertEqual(command_lists_home(command), drop)
                record = {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": "h1",
                                "type": "function",
                                "function": {
                                    "name": "run_command",
                                    "arguments": json.dumps({"command": command}),
                                },
                            }],
                        },
                        {"role": "tool", "tool_call_id": "h1", "content": listing},
                    ]
                }
                cleaned, hits = redact_record(record)
                self.assertEqual(hits, [])
                body = cleaned["messages"][1]["content"]
                if drop:
                    self.assertEqual(body, "[home directory listing removed]")
                else:
                    self.assertNotEqual(body, "[home directory listing removed]")
                    self.assertIn("<user>_cnsvs-network/", body)
                self.assertNotIn("mrhinkle", json.dumps(cleaned).lower())
                self.assertNotIn("markhinkle", json.dumps(cleaned).lower())

    def test_host_absolute_paths_keep_repo_relative(self):
        samples = (
            "cwd=/var/folders/zz/secret-user/project",
            "disk=/Volumes/Secret/proj",
            "bin=/opt/homebrew/bin/python",
            "cellar=/usr/local/lib/x",
            "tmp=/tmp/abc/def",
            "pt=/private/tmp/abc",
            "pv=/private/var/folders/xx/yy",
        )
        for sample in samples:
            with self.subTest(sample=sample[:24]):
                cleaned = redact_text(sample)
                self.assertNotIn("/var/folders", cleaned)
                self.assertNotIn("/Volumes", cleaned)
                self.assertNotIn("/opt/homebrew", cleaned)
                self.assertNotIn("/usr/local", cleaned)
                self.assertNotIn("/private/tmp", cleaned)
                self.assertNotIn("/private/var", cleaned)
                self.assertNotIn("/tmp/", cleaned)
                self.assertIn("<abs>/\u2026", cleaned)
                self.assertEqual(residual_names(cleaned), [])
                self.assertEqual(redact_text(cleaned), cleaned)
        relative = redact_text("src/tmp/file.py and ./notes/var/folders/readme and ./tmp/out.bin")
        self.assertIn("src/tmp/file.py", relative)
        self.assertIn("./notes/var/folders/readme", relative)
        self.assertIn("./tmp/out.bin", relative)
        self.assertNotIn("<abs>", relative)
        glued = (
            "at ../../../../var/folders/tw/abc/T/tmp.x:1 "
            "file:///private/tmp/gibson-review/eval "
            "ls -la /Volumes 2>/dev/null "
            "diskutil info /System/Volumes/Data "
            "n/Volumes/Mac "
            "true\\n/opt/homebrew/bin/git "
            "/usr/local/bin/git "
            "/private/var/db "
        )
        cleaned = redact_text(glued)
        for needle in ("/var/folders", "/Volumes", "/opt/homebrew", "/usr/local", "/private/tmp", "/private/var"):
            self.assertNotIn(needle, cleaned)
        self.assertIn("<abs>/\u2026", cleaned)
        self.assertEqual(residual_names(cleaned), [])
        self.assertEqual(redact_text(cleaned), cleaned)


if __name__ == "__main__":
    unittest.main()
