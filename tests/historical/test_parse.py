"""Parser tests for historical sessions. Uses the evaluation fixtures and synthetic shapes."""
from __future__ import annotations

import csv
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import training.historical.extract as extract_mod
from training.historical.extract import (  # noqa: E402
    build_task,
    classify_session_role,
    episode_base,
    format_issue_task,
    IssueStore,
    holdout_pr_keys,
    main,
    output_allowed,
    parse_session,
    resolve_user_task,
    sample_training_episodes,
    session_provenance,
    split_windows,
    truncate_tool_outputs,
)
from training.historical.validate import check_record, estimate_tokens, messages_tokens  # noqa: E402

FX = ROOT / "tests" / "evaluation" / "fixtures"
HF = Path(__file__).resolve().parent / "fixtures"


def _blob(messages):
    return json.dumps(messages)


class ParseTests(unittest.TestCase):
    def test_real_fixtures_all_vendors(self):
        for name, vendor in (
            ("claude.real.jsonl", "claude"),
            ("grok.real.jsonl", "grok"),
            ("codex.real.jsonl", "codex"),
        ):
            with self.subTest(vendor=name):
                messages = parse_session(FX / name, vendor)
                calls = [call for message in messages for call in message.get("tool_calls", [])]
                self.assertEqual([call["function"]["name"] for call in calls], ["run_command"])
                tool = next(message for message in messages if message["role"] == "tool")
                self.assertIn("hello fixture", tool["content"])
                self.assertNotIn("[104,", tool["content"])
                self.assertEqual(messages[-1]["content"].strip(), "DONE")

    def test_claude_stream_and_codex_exec_shapes(self):
        stream = parse_session(FX / "claude.stream.jsonl", "claude")
        self.assertEqual([message["role"] for message in stream], ["assistant", "tool", "assistant", "tool", "assistant"])
        self.assertEqual(stream[0]["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(stream[2]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertEqual(stream[3]["content"], "42 passed")
        self.assertEqual(stream[-1]["content"], "Fixed. 42 tests pass.")

        codex = parse_session(FX / "codex.jsonl", "codex")
        self.assertEqual(codex[0]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertIn("[exit_code=1]", codex[1]["content"])
        self.assertEqual(codex[2]["content"], "Done, all tests pass.")

    def test_codex_rollout_skips_developer_and_reasoning(self):
        messages = parse_session(HF / "codex.rollout.jsonl", "codex")
        blob = _blob(messages)
        self.assertNotIn("big instructions", blob)
        self.assertNotIn("ciphertext", blob)
        self.assertNotIn("mrhinkle", blob)
        self.assertIn("Fix the bug", blob)
        self.assertEqual(messages[1]["tool_calls"][0]["function"]["name"], "run_command")
        args = json.loads(messages[1]["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(args["command"], "cat note.txt")
        self.assertIn("hello fixture", messages[2]["content"])
        self.assertEqual(messages[3]["content"], "DONE")
        self.assertEqual(messages[4]["tool_calls"][0]["function"]["name"], "other:wait")
        self.assertEqual(messages[5]["content"], "ok")

    def test_grok_session_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            root.mkdir()
            (root / "chat_history.jsonl").write_text((HF / "grok.chat_history.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            messages = parse_session(root, "grok")
        blob = _blob(messages)
        self.assertNotIn("hidden thought", blob)
        self.assertNotIn("system reminder text", blob)
        self.assertNotIn("vendor system prompt", blob)
        self.assertEqual(messages[0]["content"], "Do the thing")
        self.assertEqual(messages[1]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertEqual(messages[2]["content"], "hello fixture")
        self.assertEqual(messages[3]["content"], "DONE")

    def test_task_uses_title_and_issue_body_when_present(self):
        row = {"repo": "the-gibson", "pr": "7", "branch": "feat/x", "issue": ""}
        pr = {
            "title": "Fix the gate",
            "headRefName": "feat/x",
            "number": 7,
            "closingIssuesReferences": [{
                "number": 9,
                "body": "The gate fails closed.",
                "repository": {"name": "the-gibson"},
            }],
        }
        text = build_task(row, pr)
        self.assertIn("Fix the gate", text)
        self.assertIn("The gate fails closed.", text)
        self.assertIn("#9", text)

    def test_task_falls_back_when_title_and_body_are_absent(self):
        row = {"repo": "conference-os", "pr": "12", "branch": "", "issue": "4"}
        pr = {
            "headRefName": "feat/twelve",
            "number": 12,
            "closingIssuesReferences": [{
                "number": 4,
                "url": "https://github.com/The-AIE/conference-os/issues/4",
                "repository": {"name": "conference-os"},
            }],
        }
        text = build_task(row, pr)
        self.assertIn("conference-os#12", text)
        self.assertIn("feat/twelve", text)
        self.assertIn("#4", text)
        self.assertNotIn("The gate", text)

    def test_output_path_allowlist(self):
        self.assertTrue(output_allowed(Path(tempfile.gettempdir()) / "historical.jsonl"))
        self.assertFalse(output_allowed(Path("/etc/historical.jsonl")))

    def test_provenance_is_url_plus_path_hash(self):
        path = "/tmp/session-not-stored"
        prov = session_provenance(path)
        self.assertTrue(prov.startswith("session:"))
        self.assertNotIn(path, prov)
        self.assertEqual(len(prov.split(":", 1)[1]), 16)
        self.assertEqual(episode_base({"vendor": "codex", "session_id": "s", "repo": "the-gibson", "pr": "1"}),
                         episode_base({"vendor": "codex", "session_id": "s", "repo": "the-gibson", "pr": "1"}))

    def test_truncates_tool_output_and_splits_episode(self):
        stats = {
            "tool_outputs_seen": 0,
            "tool_outputs_truncated": 0,
            "tool_outputs_kept": 0,
            "tool_tokens_before": 0,
            "tool_tokens_after": 0,
            "orphan_tools": 0,
            "over_context": 0,
        }
        long = "x" * 20000
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task line"},
        ]
        for i in range(4):
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": f"t{i}",
                    "type": "function",
                    "function": {"name": "run_command", "arguments": "{}"},
                }],
            })
            messages.append({"role": "tool", "tool_call_id": f"t{i}", "content": long})
        truncate_tool_outputs(messages, stats, limit=80)
        self.assertEqual(stats["tool_outputs_truncated"], 4)
        self.assertLess(stats["tool_tokens_after"], stats["tool_tokens_before"])
        for message in messages:
            if message["role"] == "tool":
                self.assertLessEqual(estimate_tokens(message["content"]), 80)
        windows = split_windows(messages, 220, stats)
        self.assertGreater(len(windows), 1)
        for window in windows:
            self.assertEqual(window[0]["role"], "system")
            self.assertEqual(window[1]["role"], "user")
            self.assertLessEqual(messages_tokens(window), 220)

    def test_pipeline_writes_private_jsonl_and_refuses_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "session.jsonl"
            session.write_text((HF / "secrets.claude.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            missing = root / "missing.jsonl"
            inventory = root / "inventory"
            inventory.mkdir()
            for name in ("prs.conference-os.json", "prs.chatterbuilt.json", "prs.the-gibson.json"):
                (inventory / name).write_text("[]", encoding="utf-8")
            (inventory / "prs.the-gibson.json").write_text(json.dumps([{
                "number": 7,
                "state": "MERGED",
                "headRefName": "feat/x",
                "title": "Fix the gate",
                "closingIssuesReferences": [{
                    "number": 9,
                    "body": "The gate fails closed.",
                    "url": "https://github.com/The-AIE/the-gibson/issues/9",
                    "repository": {"name": "the-gibson"},
                }],
            }]), encoding="utf-8")
            csv_path = root / "sessions.csv"
            fields = ["host", "vendor", "session_id", "repo", "issue", "branch", "started", "ended",
                      "tool_calls", "model", "kind", "bytes", "cwd", "path", "pr", "pr_state", "join"]
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "host": "MacBook-Pro-4", "vendor": "claude", "session_id": "s1",
                    "repo": "the-gibson", "issue": "9", "branch": "feat/x",
                    "path": str(session), "pr": "7", "pr_state": "MERGED", "join": "branch",
                })
                writer.writerow({
                    "host": "MacBook-Pro-4", "vendor": "claude", "session_id": "s2",
                    "repo": "the-gibson", "issue": "9", "branch": "feat/x",
                    "path": str(missing), "pr": "7", "pr_state": "MERGED", "join": "branch",
                })
                writer.writerow({
                    "host": "Marks-Mac-mini", "vendor": "codex", "session_id": "s3",
                    "repo": "the-gibson", "issue": "9", "branch": "feat/x",
                    "path": "/nope", "pr": "7", "pr_state": "MERGED", "join": "branch",
                })
            out = root / "out" / "historical.jsonl"
            stats = root / "STATS.md"
            code = main([
                "--csv", str(csv_path),
                "--prs-dir", str(inventory),
                "--out", str(out),
                "--stats", str(stats),
                "--max-tool-tokens", "50",
                "--max-episode-tokens", "4000",
            ])
            self.assertEqual(code, 0, stats.read_text(encoding="utf-8") if stats.exists() else "no stats")
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            blob = out.read_text(encoding="utf-8")
            for secret in (
                "sk-FAKE", "op://", "fakefakefakefake12", "mrhinkle", "ada@example.com",
                "BEGIN OPENSSH", "supersecretvalue", "ghp_FAKE", "user:password", "MacBook-Pro-4",
            ):
                self.assertNotIn(secret, blob)
            record = json.loads(blob.splitlines()[0])
            self.assertEqual(record["outcome"], "merged")
            self.assertEqual(record["messages"][0]["role"], "system")
            self.assertIn("Fix the gate", record["messages"][1]["content"])
            self.assertIn("The gate fails closed.", record["task"])
            self.assertTrue(record["provenance"][0].endswith("/the-gibson/pull/7"))
            self.assertTrue(record["provenance"][1].startswith("session:"))
            self.assertNotIn(str(session), json.dumps(record["provenance"]))
            self.assertEqual(check_record(record), [])
            text = stats.read_text(encoding="utf-8")
            self.assertIn("Usable episodes", text)
            self.assertIn("| 1 |", text)
            self.assertNotIn("mrhinkle", text)

            git_root = root / "repo"
            git_root.mkdir()
            subprocess.check_call(["git", "init", "-q", str(git_root)])
            refused = main([
                "--csv", str(csv_path),
                "--prs-dir", str(inventory),
                "--out", str(git_root / "leak.jsonl"),
                "--stats", str(root / "STATS2.md"),
            ])
            self.assertEqual(refused, 2)
            self.assertFalse((git_root / "leak.jsonl").exists())
            record = json.loads(blob.splitlines()[0])
            self.assertIn(record["session_role"], ("builder", "reviewer", "other"))

    def test_scripts_print_usage_from_repo_root(self):
        for script in ("validate.py", "extract.py", "redact.py"):
            with self.subTest(script=script):
                proc = subprocess.run(
                    [sys.executable, f"training/historical/{script}"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                blob = proc.stdout + proc.stderr
                self.assertNotIn("ModuleNotFoundError", blob)
                self.assertIn("usage", blob.lower())
                self.assertIn(f"python3 training/historical/{script}", blob)

    def test_role_from_tool_calls_keywords_only_break_ties(self):
        write = [{
            "role": "user",
            "content": "<user_query>\nLENS: VERIFICATION\n</user_query>",
        }, {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {"name": "edit_file", "arguments": "{\"path\":\"a.ts\"}"},
            }],
        }, {
            "role": "tool",
            "tool_call_id": "1",
            "content": "The file a.ts has been updated successfully.",
        }]
        # A read-only reviewer who attempted an edit is not a builder.
        self.assertEqual(classify_session_role(write, "read-only"), "reviewer")
        writable = [{
            "role": "user",
            "content": "<user_query>\nImplement the gate.\n</user_query>",
        }, write[1], write[2]]
        self.assertEqual(classify_session_role(writable, "workspace-write"), "builder")
        failed = [{
            "role": "user",
            "content": "<user_query>\nImplement the gate.\n</user_query>",
        }, write[1], {
            "role": "tool",
            "tool_call_id": "1",
            "content": "<tool_use_error>String to replace not found in file.</tool_use_error>",
        }]
        self.assertEqual(classify_session_role(failed, None), "other")
        unchanged = [{
            "role": "user",
            "content": "<user_query>\nImplement the gate.\n</user_query>",
        }, write[1], {
            "role": "tool",
            "tool_call_id": "1",
            "content": "Old string and new string are the same",
        }]
        self.assertEqual(classify_session_role(unchanged, "workspace-write"), "other")
        flagged = [{
            "role": "user",
            "content": "<user_query>\ncodex exec -s read-only\nReview the diff.\n</user_query>",
        }, write[1], write[2]]
        self.assertEqual(classify_session_role(flagged, None), "reviewer")

        commit = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {
                    "name": "run_command",
                    "arguments": json.dumps({"command": "git add a.ts && git commit -m \"fix the gate\""}),
                },
            }],
        }]
        self.assertEqual(classify_session_role(commit, None), "builder")
        self.assertEqual(classify_session_role(commit, "read-only"), "reviewer")

        mention = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {
                    "name": "run_command",
                    "arguments": json.dumps({"command": "rg \"git commit\" src"}),
                },
            }],
        }]
        self.assertEqual(classify_session_role(mention, None), "other")

        patch = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {
                    "name": "run_command",
                    "arguments": json.dumps({
                        "command": "const patch = \"*** Begin Patch\\n*** Update File: a.ts\\n@@\\n+x\\n\"",
                    }),
                },
            }],
        }, {
            "role": "tool",
            "tool_call_id": "1",
            "content": "Success. Updated the following files:\nM a.ts\n[exit_code=0]",
        }]
        self.assertEqual(classify_session_role(patch, "workspace-write"), "builder")
        patch_failed = [patch[0], {
            "role": "tool",
            "tool_call_id": "1",
            "content": "apply_patch verification failed: context mismatch\n[exit_code=1]",
        }]
        self.assertEqual(classify_session_role(patch_failed, "workspace-write"), "other")

        readonly = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {"name": "run_command", "arguments": json.dumps({"command": "git diff"})},
            }],
        }]
        self.assertEqual(classify_session_role(readonly, "read-only"), "reviewer")

        lens = [{
            "role": "user",
            "content": "rules mention spec-review inside the repo contract",
        }, {
            "role": "user",
            "content": "<user_query>\nLENS: VERIFICATION. Can the spec be proved?\n</user_query>",
        }, {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {"name": "read_file", "arguments": "{}"},
            }],
        }]
        self.assertEqual(classify_session_role(lens, None), "reviewer")

        author = [{
            "role": "user",
            "content": "<user_query>\nYou are the implementation author. Edit the files.\n</user_query>",
        }, {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "1",
                "type": "function",
                "function": {"name": "read_file", "arguments": "{}"},
            }],
        }]
        self.assertEqual(classify_session_role(author, None), "other")

    def test_issue_task_truncates_and_fetch_failure_keeps_header(self):
        title = "Fix the gate"
        body = "x" * 1800
        text = format_issue_task(title, body)
        self.assertTrue(text.startswith("Fix the gate\n\n"))
        self.assertEqual(len(text.split("\n\n", 1)[1]), 1500)

        row = {"repo": "conference-os", "pr": "12", "branch": "", "issue": "4"}
        pr = {
            "headRefName": "feat/twelve",
            "number": 12,
            "closingIssuesReferences": [{
                "number": 4,
                "url": "https://github.com/The-AIE/conference-os/issues/4",
                "repository": {"name": "conference-os"},
            }],
        }

        class EmptyStore:
            def get(self, repo, number):
                return None

        task, source = resolve_user_task(row, pr, EmptyStore())
        self.assertEqual(source, "fallback")
        self.assertIn("conference-os#12", task)
        self.assertIn("#4", task)

        class HitStore:
            def get(self, repo, number):
                return {"title": "Real title", "body": "Real body " + ("y" * 2000)}

        fetched, source = resolve_user_task(row, pr, HitStore())
        self.assertEqual(source, "fetched")
        self.assertTrue(fetched.startswith("Real title\n\nReal body"))
        self.assertEqual(len(fetched.split("\n\n", 1)[1]), 1500)
        self.assertNotIn("feat/twelve", fetched)

    def test_issue_fetch_parses_colorized_gh_json(self):
        colored = (
            '\x1b[1;37m{\x1b[m\n'
            '  \x1b[1;34m"title"\x1b[m: \x1b[32m"Fix the gate"\x1b[m,\n'
            '  \x1b[1;34m"body"\x1b[m: \x1b[32m"The gate fails closed."\x1b[m\n'
            '}\x1b[m\n'
        )

        class Proc:
            returncode = 0
            stdout = colored
            stderr = ""

        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs.get("env") or {}
            return Proc()

        real = extract_mod.subprocess.run
        extract_mod.subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as tmp:
                store = IssueStore(Path(tmp))
                data = store.get("conference-os", 4)
                cached = Path(tmp) / "conference-os-4.json"
                self.assertTrue(cached.is_file())
                self.assertEqual(stat.S_IMODE(cached.stat().st_mode), 0o600)
        finally:
            extract_mod.subprocess.run = real
        self.assertEqual(data["title"], "Fix the gate")
        self.assertEqual(data["body"], "The gate fails closed.")
        self.assertEqual(seen["env"].get("GH_FORCE_TTY"), "0")
        self.assertEqual(seen["env"].get("NO_COLOR"), "1")
        self.assertIn("4", seen["cmd"])

    def test_holdout_is_latest_builder_prs_and_sample_keeps_small_repos(self):
        episodes = [
            {
                "key": f"e{i}",
                "repo": "conference-os",
                "pr": i,
                "merged_at": f"2026-01-{i:02d}T00:00:00Z",
                "vendor": "codex" if i % 2 else "grok",
                "tokens": 60,
                "windows": 1,
                "role": "builder",
            }
            for i in range(1, 11)
        ]
        episodes.append({
            "key": "undated",
            "repo": "conference-os",
            "pr": 99,
            "merged_at": "",
            "vendor": "codex",
            "tokens": 60,
            "windows": 1,
            "role": "builder",
        })
        held = holdout_pr_keys(episodes, 0.15)
        self.assertEqual(held, {("conference-os", 9), ("conference-os", 10)})
        self.assertNotIn(("conference-os", 99), held)

        pool = [
            {"key": "g", "repo": "the-gibson", "vendor": "codex", "tokens": 100, "pr": 1},
            {"key": "c", "repo": "chatterbuilt", "vendor": "grok", "tokens": 100, "pr": 2},
            {"key": "a", "repo": "conference-os", "vendor": "codex", "tokens": 60, "pr": 3},
            {"key": "b", "repo": "conference-os", "vendor": "grok", "tokens": 60, "pr": 4},
            {"key": "d", "repo": "conference-os", "vendor": "codex", "tokens": 60, "pr": 5},
        ]
        capped = sample_training_episodes(pool, cap=200, seed=414)
        self.assertEqual({item["key"] for item in capped}, {"g", "c"})
        wider = sample_training_episodes(pool, cap=320, seed=414)
        keys = {item["key"] for item in wider}
        self.assertTrue({"g", "c"} <= keys)
        self.assertLessEqual(sum(item["tokens"] for item in wider), 320)
        vendors = {item["vendor"] for item in wider if item["repo"] == "conference-os"}
        self.assertEqual(vendors, {"codex", "grok"})


if __name__ == "__main__":
    unittest.main()
