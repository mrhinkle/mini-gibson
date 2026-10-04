"""Run: python -m unittest discover -s hackathon/flight-recorder/tests"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRAFT = HERE.parent / "draft"
FX = HERE / "fixtures"
sys.path.insert(0, str(DRAFT))
import trace_export as te  # noqa: E402

HAVE_JQ = shutil.which("jq") is not None


def make_run(root, repo, day, run_id, record, files):
    d = Path(root) / "clean" / repo / day / run_id
    d.mkdir(parents=True)
    (d / "record.json").write_text(json.dumps(record))
    for name, src in files.items():
        shutil.copy(src, d / name) if isinstance(src, Path) else (d / name).write_text(src)
    return d


class ExportTests(unittest.TestCase):
    def test_claude_stream_to_messages(self):
        m = te.claude_messages(FX / "claude.stream.jsonl")
        roles = [x["role"] for x in m]
        self.assertEqual(roles, ["assistant", "tool", "assistant", "tool", "assistant"])
        self.assertEqual(m[0]["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(m[2]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertEqual(m[3]["content"], "42 passed")
        self.assertEqual(m[-1]["content"], "Fixed. 42 tests pass.")  # result event not duplicated

    def test_codex_to_messages(self):
        m = te.codex_messages(FX / "codex.jsonl")
        self.assertEqual(m[0]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertIn("[exit_code=1]", m[1]["content"])
        self.assertEqual(m[2]["content"], "Done, all tests pass.")

    def test_real_fixtures_all_vendors(self):
        # Real runs captured 2026-10-04 (claude 2.1.289, codex-cli 0.154.0, grok 1.0.13), paths scrubbed.
        # Same prompt for each: run `cat note.txt`, then reply DONE.
        for name, fn in (("claude.real.jsonl", te.claude_messages), ("grok.real.jsonl", te.claude_messages),
                         ("codex.real.jsonl", te.codex_messages)):
            with self.subTest(vendor=name):
                m = fn(FX / name)
                calls = [c for x in m for c in x.get("tool_calls", [])]
                self.assertEqual([c["function"]["name"] for c in calls], ["run_command"])
                tool = next(x for x in m if x["role"] == "tool")
                self.assertIn("hello fixture", tool["content"])
                self.assertNotIn("[104,", tool["content"])  # grok byte-array envelope decoded
                self.assertEqual(m[-1]["content"].strip(), "DONE")

    def test_unknown_tool_passthrough(self):
        self.assertEqual(te.norm_tool("WebFetch"), "other:WebFetch")

    def test_labels(self):
        L = te.label_of
        self.assertEqual(L({"labels": {"harness": {"gate_exit": 0}}}), "verified")
        self.assertEqual(L({"labels": {"harness": {"gate_exit": 1, "premature_completion": True}}}), "premature_completion")
        self.assertEqual(L({"labels": {"harness": {"gate_exit": 1}}}), "failed_honest")
        self.assertEqual(L({"labels": {"harness": {"gate_exit": 0, "test_integrity": {"ok": False}}}}), "test_tampering")
        self.assertEqual(L({}), "unlabeled")

    def test_split_filter_freeze_and_leak_refusal(self):
        with tempfile.TemporaryDirectory() as t:
            root, out = Path(t, "traces"), Path(t, "out")
            ok = {"labels": {"harness": {"gate_exit": 0}}}
            liar = {"labels": {"harness": {"gate_exit": 1, "premature_completion": True}}}
            make_run(root, "cos", "2026-10-06", "r1", {"run_id": "r1", "runner": "claude", "started_at": "2026-10-06T10:00:00Z", **ok},
                     {"events.claude.jsonl": FX / "claude.stream.jsonl", "prompt.md": "Fix the date bug"})
            make_run(root, "cos", "2026-10-07", "r2", {"run_id": "r2", "runner": "codex", "started_at": "2026-10-07T10:00:00Z", **liar},
                     {"events.codex.jsonl": FX / "codex.jsonl"})
            make_run(root, "cos", "2026-10-13", "r3", {"run_id": "r3", "runner": "claude", "started_at": "2026-10-13T10:00:00Z", **ok},
                     {"events.claude.jsonl": FX / "claude.stream.jsonl"})
            # raw/ must be ignored entirely
            (root / "raw" / "cos").mkdir(parents=True)
            (root / "raw" / "cos" / "record.json").write_text(json.dumps({"run_id": "SECRET", **ok}))

            self.assertEqual(te.main(["--root", str(root), "--cutoff", "2026-10-12", "--out", str(out), "--only-verified", "--freeze"]), 0)
            train = [json.loads(l) for l in (out / "train.jsonl").read_text().splitlines()]
            held = [json.loads(l) for l in (out / "heldout.jsonl").read_text().splitlines()]
            self.assertEqual([r["run_id"] for r in train], ["r1"])
            self.assertEqual([r["run_id"] for r in held], ["r3"])
            self.assertEqual(train[0]["messages"][0], {"role": "user", "content": "Fix the date bug"})
            self.assertNotIn("SECRET", (out / "train.jsonl").read_text())

            te.main(["--root", str(root), "--cutoff", "2026-10-12", "--out", str(out), "--premature"])
            labels = {json.loads(l)["run_id"]: json.loads(l)["label"] for l in (out / "train.jsonl").read_text().splitlines()}
            self.assertEqual(labels["r2"], "premature_completion")

            # moving the cutoff later must not move the frozen r3 into train
            te.main(["--root", str(root), "--cutoff", "2026-12-31", "--out", str(out)])
            train_ids = [json.loads(l)["run_id"] for l in (out / "train.jsonl").read_text().splitlines()]
            held_ids = [json.loads(l)["run_id"] for l in (out / "heldout.jsonl").read_text().splitlines()]
            self.assertNotIn("r3", train_ids)
            self.assertIn("r3", held_ids)


def _stub(dirpath, name, body):
    p = Path(dirpath) / name
    p.write_text("#!/usr/bin/env bash\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


@unittest.skipUnless(HAVE_JQ, "jq required")
class TraceShellTests(unittest.TestCase):
    def run_bash(self, script, env):
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)

    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.bin = Path(self.t, "bin"); self.bin.mkdir()
        self.repo = Path(self.t, "repo"); self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        stream = (FX / "claude.stream.jsonl").read_text().replace("'", "'\\''")
        _stub(self.bin, "claude", f"""for a in "$@"; do [[ "$a" == stream-json ]] && {{ printf '%s' '{stream}'; exit 0; }}; done
echo 'Fixed. 42 tests pass.'""")
        self.prompt = Path(self.t, "prompt.md"); self.prompt.write_text("---\nrole: builder\n---\nFix it")
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "GIBSON_TRACE_ROOT": str(Path(self.t, "traces")), "HOME": self.t}
        self.pre = f"run_with_wall_timeout() {{ shift; \"$@\"; }}; . {DRAFT}/trace.sh; "

    def tearDown(self):
        shutil.rmtree(self.t)

    def test_byte_identical_handoff_and_record(self):
        off = self.run_bash(self.pre + f"GIBSON_TRACE=0; trace_begin --repo {self.repo} --runner claude --role builder --prompt-file {self.prompt}; trace_run_claude 60 {self.repo} {self.prompt}", self.env)
        on = self.run_bash(self.pre + f"trace_begin --repo {self.repo} --runner claude --role builder --issue 42 --prompt-file {self.prompt}; "
                           f"trace_run_claude 60 {self.repo} {self.prompt}; rc=$?; trace_end $rc --gate-exit 1 --claimed success", self.env)
        self.assertEqual(off.stdout, on.stdout)  # AC #1.4: loop sees the same text
        recs = list(Path(self.t, "traces", "raw").rglob("record.json"))
        self.assertEqual(len(recs), 1)
        rec = json.loads(recs[0].read_text())
        self.assertEqual(rec["issue"], "42")
        self.assertEqual(rec["trace_status"], "ok")
        self.assertTrue(rec["labels"]["harness"]["premature_completion"])
        self.assertTrue((recs[0].parent / "events.claude.jsonl").exists())
        self.assertTrue((recs[0].parent / "prompt.md").exists())

    def test_refuses_root_inside_git_worktree(self):
        env = {**self.env, "GIBSON_TRACE_ROOT": str(self.repo / "traces")}
        r = self.run_bash(self.pre + f"trace_begin --repo {self.repo} --runner claude --role builder --prompt-file {self.prompt}; echo status=$TRACE_STATUS; "
                          f"trace_run_claude 60 {self.repo} {self.prompt}", env)
        self.assertIn("status=failed", r.stdout)
        self.assertIn("Fixed. 42 tests pass.", r.stdout)  # run still works
        self.assertFalse((self.repo / "traces" / "raw").exists())

    def test_kill_switch(self):
        r = self.run_bash(self.pre + f"GIBSON_TRACE=0; trace_begin --repo {self.repo} --runner claude --role builder --prompt-file {self.prompt}; echo on=$TRACE_ON", self.env)
        self.assertIn("on=0", r.stdout)
        self.assertFalse(Path(self.t, "traces").exists())


class ScrubTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.root = Path(self.t, "traces")
        self.raw = self.root / "raw" / "cos" / "2026-10-06" / "r1"
        self.raw.mkdir(parents=True)
        (self.raw / "events.claude.jsonl").write_text(
            '{"cmd":"cat /Users/mrhinkle/.env","out":"OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwx ok"}\n'
            '{"out":"mail mark@example.com token ghp_abcdefghijklmnopqrstuvwxyz0123 DATABASE_URL postgres://u:p@host/db"}\n'
            '{"out":"Authorization: Bearer abcdefghijklmnop1234"}\n')
        self.bin = Path(self.t, "bin"); self.bin.mkdir()

    def tearDown(self):
        shutil.rmtree(self.t)

    def scrub(self, gitleaks_rc=None):
        path = os.environ["PATH"]
        if gitleaks_rc is not None:
            _stub(self.bin, "gitleaks", f"exit {gitleaks_rc}\n")
            path = f"{self.bin}:{path}"
        else:
            path = ":".join(p for p in path.split(":") if not (Path(p) / "gitleaks").exists())
        env = {**os.environ, "PATH": path, "GIBSON_TRACE_ROOT": str(self.root), "HOME": "/Users/mrhinkle"}
        env.pop("GIBSON_ROOT", None)
        return subprocess.run(["bash", str(DRAFT / "trace-scrub.sh"), str(self.raw)], capture_output=True, text=True, env=env)

    def test_redacts_when_gitleaks_clean(self):
        r = self.scrub(gitleaks_rc=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = (self.root / "clean" / "cos" / "2026-10-06" / "r1" / "events.claude.jsonl").read_text()
        for secret in ("mrhinkle", "sk-abcdefghij", "mark@example.com", "ghp_abcdef", "u:p@host", "abcdefghijklmnop1234"):
            self.assertNotIn(secret, out)
        self.assertIn("~/.env", out)

    def test_quarantines_on_finding(self):
        r = self.scrub(gitleaks_rc=1)
        self.assertEqual(r.returncode, 3)
        self.assertFalse((self.root / "clean").exists())
        self.assertTrue((self.root / "quarantine" / "cos" / "2026-10-06" / "r1").exists())

    def test_fails_closed_without_gitleaks(self):
        r = self.scrub(gitleaks_rc=None)
        self.assertEqual(r.returncode, 4)
        self.assertFalse((self.root / "clean").exists())


if __name__ == "__main__":
    unittest.main()
