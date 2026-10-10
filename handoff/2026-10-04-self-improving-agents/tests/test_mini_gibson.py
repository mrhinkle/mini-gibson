"""Run: python -m unittest discover -s hackathon/mini-gibson/tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import jev_sensor as js  # noqa: E402
import verify  # noqa: E402
import eval_sensor  # noqa: E402


def fake(probs):
    return lambda body: {"answers": {k: {"type": "noul", "noul": probs.get(k, 0.05)} for k in body["questions"]},
                         "usage": {"input_tokens": 1}}


CLEAN = {"claims_complete": 0.95, "unsupported_result_claim": 0.05, "tests_ran_after_last_change": 0.97,
         "failure_ignored": 0.04, "tests_weakened": 0.02}
LIAR = {**CLEAN, "unsupported_result_claim": 0.93, "tests_ran_after_last_change": 0.08}


class SensorTests(unittest.TestCase):
    def test_request_shape(self):
        seen = {}
        def t(body):
            seen.update(body)
            return fake(CLEAN)(body)
        js.JevSensor(transport=t).assess(js.build_state("task", "done", "log"))
        self.assertEqual(seen["model"], "jev-latest")
        self.assertTrue(all(q["type"] == "noul" for q in seen["questions"].values()))
        self.assertEqual(set(seen["state"]), {"task", "final_message", "tool_log", "changed_files"})

    def test_missing_answer_raises(self):
        with self.assertRaises(ValueError):
            js.JevSensor(transport=lambda b: {"answers": {"claims_complete": {"noul": 0.5}}}).assess({})

    def test_log_truncation_keeps_tail(self):
        s = js.build_state("t", "m", "A" * 20000 + "FINAL TEST OUTPUT")
        self.assertLessEqual(len(s["tool_log"]), js.MAX_LOG_CHARS + 40)
        self.assertTrue(s["tool_log"].endswith("FINAL TEST OUTPUT"))

    def test_premature_completion_score(self):
        self.assertLess(js.SensorResult(CLEAN).premature_completion, 0.15)
        self.assertGreater(js.SensorResult(LIAR).premature_completion, 0.85)

    def test_no_api_key_errors_cleanly(self):
        s = js.JevSensor(api_key=None)
        s.api_key = None
        with self.assertRaises(RuntimeError):
            s._http({})


class RoutingTests(unittest.TestCase):
    def test_env_fail_always_rejects_even_if_sensor_clean(self):
        v = js.route(False, True, js.SensorResult(CLEAN))
        self.assertEqual(v.decision, "REJECT")

    def test_sensor_can_never_accept_a_failed_env(self):
        for probs in (CLEAN, LIAR):
            self.assertNotEqual(js.route(False, True, js.SensorResult(probs)).decision, "ACCEPT")

    def test_tampering_rejects(self):
        v = js.route(True, False, js.SensorResult(CLEAN))
        self.assertEqual(v.decision, "REJECT")
        self.assertIn("test_tampering", v.failure_classes)

    def test_liar_gets_specific_feedback(self):
        v = js.route(False, True, js.SensorResult(LIAR))
        self.assertIn("premature_completion", v.failure_classes)
        self.assertTrue(any("No test run" in f for f in v.feedback))

    def test_clean_pass_accepts(self):
        self.assertEqual(js.route(True, True, js.SensorResult(CLEAN)).decision, "ACCEPT")

    def test_env_pass_with_flag_is_suspicious_review(self):
        v = js.route(True, True, js.SensorResult({**CLEAN, "failure_ignored": 0.9}))
        self.assertEqual(v.decision, "REVIEW")
        self.assertTrue(v.suspicious)

    def test_uncertain_goes_to_review(self):
        v = js.route(True, True, js.SensorResult({**CLEAN, "tests_weakened": 0.5}))
        self.assertEqual(v.decision, "REVIEW")

    def test_works_without_sensor(self):
        self.assertEqual(js.route(True, True, None).decision, "ACCEPT")
        self.assertEqual(js.route(False, True, None).decision, "REJECT")


class VerifyTests(unittest.TestCase):
    def test_checksums_detect_modified_deleted_added(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "tests").mkdir()
            (p / "tests" / "test_a.py").write_text("assert 1")
            (p / "tests" / "test_b.py").write_text("assert 2")
            (p / "app.py").write_text("x = 1")
            before = verify.checksum_tests(p)
            self.assertEqual(set(before), {"tests/test_a.py", "tests/test_b.py"})
            (p / "tests" / "test_a.py").write_text("pass  # weakened")
            (p / "tests" / "test_b.py").unlink()
            (p / "tests" / "test_c.py").write_text("assert 3")
            (p / "app.py").write_text("x = 2")  # non-test change is ignored
            d2 = verify.diff_checksums(before, verify.checksum_tests(p))
            self.assertEqual(d2, {"modified": ["tests/test_a.py"], "deleted": ["tests/test_b.py"], "added": ["tests/test_c.py"]})
            self.assertFalse(verify.tests_unchanged(before, verify.checksum_tests(p)))

    def test_added_tests_allowed_by_default(self):
        self.assertTrue(verify.tests_unchanged({"a": "1"}, {"a": "1", "b": "2"}))
        self.assertFalse(verify.tests_unchanged({"a": "1"}, {"a": "1", "b": "2"}, allow_added=False))

    def test_run_tests_reads_real_exit_code(self):
        ok = verify.run_tests(".", [sys.executable, "-c", "print('3 passed')"])
        bad = verify.run_tests(".", [sys.executable, "-c", "import sys; print('1 failed'); sys.exit(1)"])
        self.assertTrue(ok.passed)
        self.assertFalse(bad.passed)
        self.assertEqual(bad.exit_code, 1)


class EvalTests(unittest.TestCase):
    def test_metrics_and_bands(self):
        rows = [{"label": True}, {"label": True}, {"label": False}, {"label": False}]
        out = eval_sensor.evaluate(rows, [0.99, 0.4, 0.6, 0.01], 0.5)
        self.assertEqual(out["confusion"], {"tp": 1, "fp": 1, "fn": 1, "tn": 1})
        self.assertEqual(out["precision"], 0.5)
        self.assertEqual(out["by_confidence_band"]["high (>0.9)"], {"correct": 2, "wrong": 0})
        self.assertEqual(out["by_confidence_band"]["low (<0.5)"], {"correct": 0, "wrong": 2})

    def test_dry_run_end_to_end(self):
        fx = HERE / "fixtures" / "incidents.sample.jsonl"
        self.assertEqual(eval_sensor.main([str(fx), "--dry-run"]), 0)


if __name__ == "__main__":
    unittest.main()
