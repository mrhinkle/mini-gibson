import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

from adapters.jev import ENDPOINT, QUESTIONS, QUESTION_SET_VERSION, JevAdapter, JevConfig, JevError, NoRedirect, typed_answers
from experiment.decisions import DecisionService
from experiment.manifest import digest, load_manifest, policy_fingerprint, validate_manifest
from gibson_env import Action, GibsonEnv, Task, TerminalState, Verification
from telemetry.jev import JevJsonlTelemetry


def manifest(*, enabled=True, scored=False, **config):
    return {"run": {"scored": scored}, "integrations": {"jev": {"enabled": enabled, **config}}}


def response(point, **values):
    answers = {}
    for name, question in QUESTIONS[point].items():
        kind = question["type"]
        if kind == "noul":
            answers[name] = {"type": kind, "noul": values.get(name, 1.0)}
        elif kind == "choice":
            options = list(question["criteria"])
            choice = values.get(name, options[0])
            answers[name] = {"type": kind, "choice": choice, "confidence": 1.0,
                             "probabilities": {o: float(o == choice) for o in options}}
        else:
            score = values.get(name, 0.0)
            answers[name] = {"type": kind, "score": score, "confidence": 1.0,
                             "legend": {str(i): c for i, c in enumerate(question["criteria"])},
                             "probabilities": {str(i): float(i == score) for i in range(len(question["criteria"]))}}
    return {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 0}}


def service(data=None, point="tool-call-guard", result=None, telemetry=None, arm_id=None):
    adapter = Mock(spec=JevAdapter)
    adapter.request.return_value = result or response(point)
    events = []
    obj = DecisionService(manifest() if data is None else data, adapter=adapter, telemetry=telemetry or events.append, arm_id=arm_id)
    return obj, adapter, events


class ManifestTests(unittest.TestCase):
    def test_missing_extension_is_disabled_and_scored(self):
        policy = validate_manifest({})
        self.assertFalse(policy.config.enabled)
        self.assertTrue(policy.scored)

    def test_default_example_loads(self):
        self.assertFalse(load_manifest("experiment.example.yaml").config.enabled)

    def test_invalid_configuration_fails_closed(self):
        invalid = ({"enabled": "false"}, {"model": "jev-latest"}, {"model": "jev-preview"},
                   {"api_key": "secret"}, {"credentials_env": "OTHER_KEY"}, {"endpoint": "http://attacker"},
                   {"timeout_seconds": 0}, {"timeout_seconds": float("nan")}, {"min_confidence": True},
                   {"min_confidence": 0.3}, {"scored_loop": "single_arm"})
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_manifest(manifest(**config))
        for value in (None, [], "false"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_manifest({"integrations": {"jev": value}})
        with self.assertRaises(ValueError):
            validate_manifest({"run": {"scored": "false"}})

    def identical(self):
        data = manifest(scored=True, scored_loop="identical_across_all_arms")
        data["comparison"] = {"arms": [{"id": arm} for arm in "ABC"],
                              "jev_policy_sha256": policy_fingerprint(JevConfig.parse(data["integrations"]["jev"]))}
        return data

    def test_identical_frozen_three_arm_policy(self):
        data = self.identical()
        policies = [validate_manifest(data, arm) for arm in "ABC"]
        self.assertEqual(len({p.policy_sha256 for p in policies}), 1)
        data["comparison"]["arms"][0]["integrations"] = {"jev": {"timeout_seconds": 3.0}}
        validate_manifest(data, "A")  # Semantically identical defaults are accepted.

    def test_scored_one_arm_difference_is_rejected_for_every_arm(self):
        for change in ({"enabled": False}, {"model": "jev-1.14.0"}, {"timeout_seconds": 4},
                       {"min_confidence": 0.9}, {"scored_loop": "excluded_from_scored_loop"}):
            data = self.identical()
            data["comparison"]["arms"][1]["integrations"] = {"jev": change}
            for arm in "ABC":
                with self.subTest(change=change, arm=arm), self.assertRaises(ValueError):
                    validate_manifest(data, arm)

    def test_missing_frozen_hash_context_or_unique_arms_is_rejected(self):
        data = self.identical()
        with self.assertRaises(ValueError):
            validate_manifest(data)
        for mutate in (lambda d: d["comparison"].pop("jev_policy_sha256"),
                       lambda d: d["comparison"].update(jev_policy_sha256="0" * 64),
                       lambda d: d["comparison"].update(arms=[{"id": "A"}]),
                       lambda d: d["comparison"].update(arms=[{"id": "A"}, {"id": "A"}])):
            changed = copy.deepcopy(data)
            mutate(changed)
            with self.assertRaises(ValueError):
                validate_manifest(changed, "A")
        with self.assertRaises(ValueError):
            validate_manifest(data, "unknown")

    def test_semantically_equal_numeric_configs_have_identical_hashes(self):
        data = self.identical()
        data["integrations"]["jev"]["timeout_seconds"] = 3
        data["comparison"]["arms"][0]["integrations"] = {"jev": {"timeout_seconds": 3.0}}
        self.assertEqual(len({validate_manifest(data, arm).policy_sha256 for arm in "ABC"}), 1)

    def test_validation_cli_rejects_unsafe_manifest_and_never_needs_a_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest(model="jev-latest")))
            command = [sys.executable, "-m", "experiment.validate", str(path)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("must be pinned", result.stderr)
            path.write_text(json.dumps({}))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)["enabled"])

    def test_duplicate_and_invalid_yaml_fail_closed_without_echoing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.yaml"
            for text in ("integrations: {jev: {enabled: false, enabled: true}}", "private_key: [secret"):
                path.write_text(text)
                with self.assertRaises(ValueError) as caught:
                    load_manifest(path)
                self.assertNotIn("secret", str(caught.exception))

    def test_one_arm_cannot_enable_identical_service_over_disabled_root(self):
        data = self.identical()
        data["integrations"]["jev"]["enabled"] = False
        data["comparison"]["arms"][0]["integrations"] = {"jev": {"enabled": True}}
        with self.assertRaises(ValueError):
            validate_manifest(data, "B")


class TransportTests(unittest.TestCase):
    def test_official_post_bearer_timeout_and_environment_only_credentials(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(response("tool-call-guard")).encode()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-only-key"}), patch("adapters.jev.build_opener", return_value=opener):
            payload = JevConfig().payload("tool-call-guard", {"tool": "read", "permission_granted": True})
            JevAdapter().request(payload, 2.5)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, ENDPOINT)
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer test-only-key")
        self.assertEqual(json.loads(req.data), payload)
        self.assertNotIn("test-only-key", req.data.decode())
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 2.5)
        self.assertEqual(opener.open.call_count, 1)

    def test_missing_credentials_makes_no_http_attempt(self):
        with patch.dict(os.environ, {}, clear=True), patch("adapters.jev.build_opener") as opener:
            with self.assertRaisesRegex(JevError, "missing_credentials"):
                JevAdapter().request({}, 1)
            opener.assert_not_called()

    def test_redirect_is_refused_without_forwarding_credentials(self):
        with self.assertRaisesRegex(JevError, "redirect_refused"):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://attacker")

    def test_http_and_network_errors_have_no_sensitive_text_or_retry(self):
        errors = [HTTPError(ENDPOINT, 401, "secret", {}, io.BytesIO(b"secret")), URLError("secret"), TimeoutError("secret")]
        for error in errors:
            opener = MagicMock()
            opener.open.side_effect = error
            with self.subTest(error=error), patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}), patch("adapters.jev.build_opener", return_value=opener):
                with self.assertRaises(JevError) as caught:
                    JevAdapter().request({}, 0.1)
                self.assertNotIn("secret", str(caught.exception))
                self.assertEqual(opener.open.call_count, 1)

    def test_response_size_and_json_are_bounded(self):
        for body in (b"x" * 65537, b"not-json", b"[]"):
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value.read.return_value = body
            with self.subTest(size=len(body)), patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}), patch("adapters.jev.build_opener", return_value=opener):
                with self.assertRaises(JevError):
                    JevAdapter().request({}, 1)


class AdviceTests(unittest.TestCase):
    def test_disabled_and_scored_excluded_never_call_provider(self):
        for data in ({}, manifest(enabled=False), manifest(scored=True)):
            obj, adapter, events = service(data)
            obj.classify_tool_risk("read", True)
            adapter.request.assert_not_called()

    def test_enabled_requires_telemetry(self):
        with self.assertRaises(ValueError):
            DecisionService(manifest())

    def test_successful_typed_advice_and_request_metadata(self):
        obj, adapter, events = service()
        advice = obj.classify_tool_risk("read", True)
        self.assertEqual(advice.source, "jev")
        event = events[0]
        request = adapter.request.call_args.args[0]
        self.assertEqual(event["state_sha256"], digest(request["state"]))
        self.assertEqual(event["request_sha256"], digest(request))
        self.assertEqual(event["question_set_version"], QUESTION_SET_VERSION)
        self.assertEqual(event["typed_answers"], advice.answers)
        self.assertGreaterEqual(event["latency_ms"], 0)
        self.assertEqual(set(request), {"model", "state", "questions"})
        self.assertNotIn("state", event)

    def test_every_unavailable_call_uses_same_deterministic_fallback(self):
        for error in (JevError("missing_credentials"), JevError("http_429"), JevError("transport_error"), RuntimeError("private text")):
            obj, adapter, events = service()
            adapter.request.side_effect = error
            advice = obj.classify_tool_risk("read", True)
            self.assertEqual(advice.answers["allow_tool_call"]["noul"], 0)
            self.assertEqual(advice.fallback_reason, "unavailable")
            self.assertNotIn("private text", json.dumps(events))
            adapter.request.assert_called_once()

    def test_noul_uncertainty_and_choice_confidence_use_fallback(self):
        for probability in (0.5, 0.7):
            obj, _, events = service(result=response("tool-call-guard", allow_tool_call=probability))
            self.assertEqual(obj.classify_tool_risk("read", True).fallback_reason, "low_confidence")
            self.assertAlmostEqual(events[0]["confidence"], abs(2 * probability - 1))
        result = response("benchmark-anomaly-triage")
        result["answers"]["anomaly_class"]["confidence"] = 0.2
        obj, _, _ = service(point="benchmark-anomaly-triage", result=result)
        advice = obj.triage_anomaly(terminal_state="FAILED", failure_kind="task", tool_error_count=1)
        self.assertEqual(advice.answers["anomaly_class"]["choice"], "requires_human_review")

    def test_invalid_response_and_model_drift_fail_closed(self):
        for mutate in (lambda d: d.update(model="jev-latest"),
                       lambda d: d["answers"].update(generate_code={"type": "choice", "choice": "patch"}),
                       lambda d: d["answers"]["allow_tool_call"].update(noul=float("nan")),
                       lambda d: d["answers"]["allow_tool_call"].update(noul=True),
                       lambda d: d["answers"]["risk"].update(type="choice"),
                       lambda d: d["answers"]["risk"].update(score=3),
                       lambda d: d["answers"]["risk"].update(probabilities={"0": 1, "1": 1, "2": 0})):
            result = response("tool-call-guard")
            mutate(result)
            obj, _, _ = service(result=result)
            self.assertEqual(obj.classify_tool_risk("read", True).fallback_reason, "unavailable")

    def test_response_metadata_and_unknown_error_messages_are_sanitized(self):
        result = response("tool-call-guard")
        result["private_data"] = "secret response text"
        obj, _, events = service(result=result)
        obj.classify_tool_risk("read", True)
        self.assertEqual(events[0]["response_model"], "jev-1.13.0")
        self.assertEqual(events[0]["usage"], {"input_tokens": 10, "output_tokens": 0})
        self.assertNotIn("secret response text", json.dumps(events))
        obj, adapter, events = service()
        adapter.request.side_effect = JevError("secret")
        obj.classify_tool_risk("read", True)
        self.assertEqual(events[0]["error"], "adapter_error")

    def test_inconsistent_choice_and_score_are_rejected(self):
        result = response("benchmark-anomaly-triage")
        result["answers"]["anomaly_class"]["choice"] = "requires_human_review"
        with self.assertRaises(JevError):
            typed_answers(result, "benchmark-anomaly-triage", "jev-1.13.0")
        result = response("tool-call-guard")
        result["answers"]["risk"]["score"] = 1.0
        with self.assertRaises(JevError):
            typed_answers(result, "tool-call-guard", "jev-1.13.0")

    def test_no_arbitrary_questions_or_state_inputs(self):
        obj, adapter, _ = service()
        with self.assertRaises(TypeError):
            obj.classify_tool_risk("read", True, arguments={"key": "secret"})
        for terminal in ("secret", "VERIFIED secretly"):
            with self.assertRaises(ValueError):
                obj.triage_anomaly(terminal_state=terminal, failure_kind="task", tool_error_count=1)
        with self.assertRaises(ValueError):
            obj.routing_advice(current_agent="nemotron-replacement", infrastructure_healthy=True)
        obj.classify_tool_risk("secret text\n", False)
        self.assertEqual(adapter.request.call_args.args[0]["state"]["tool"], "unrecognized_tool")

    def test_scored_routing_never_calls_provider_even_with_identical_policy(self):
        data = ManifestTests().identical()
        obj, adapter, _ = service(data, arm_id="A")
        self.assertEqual(obj.routing_advice(current_agent="hermes", infrastructure_healthy=True).fallback_reason, "scored_loop_excluded")
        adapter.request.assert_not_called()
        obj.classify_tool_risk("read", True)
        adapter.request.assert_called_once()

    def test_infrastructure_advice_cannot_retry_task_or_post_execution_failure(self):
        for failure, started, allowed, healthy in (("task", False, True, False), ("infrastructure", True, True, False),
                                                   ("infrastructure", False, False, False), ("infrastructure", False, True, True)):
            obj, _, _ = service(point="supervisor-escalation", result=response("supervisor-escalation", action="retry_infrastructure"))
            advice = obj.supervisor_advice(infrastructure_healthy=healthy, failure_kind=failure, execution_started=started,
                                           infrastructure_retry_allowed=allowed, retry_count=1)
            self.assertEqual(advice.fallback_reason, "retry_not_authorized")
        obj, _, _ = service(point="supervisor-escalation", result=response("supervisor-escalation", action="retry_infrastructure"))
        advice = obj.supervisor_advice(infrastructure_healthy=False, failure_kind="infrastructure", execution_started=False,
                                       infrastructure_retry_allowed=True, retry_count=1)
        self.assertEqual(advice.source, "jev")

    def test_policy_mutation_after_validation_prevents_provider_call(self):
        obj, adapter, _ = service()
        with patch.dict(QUESTIONS["tool-call-guard"]["risk"], {"instructions": "new policy"}):
            self.assertEqual(obj.classify_tool_risk("read", True).fallback_reason, "policy_changed")
            adapter.request.assert_not_called()

    def test_permission_and_telemetry_failure_use_fallback(self):
        obj, _, _ = service()
        self.assertEqual(obj.classify_tool_risk("dangerous", False).fallback_reason, "permission_denied")
        sink = Mock(side_effect=OSError("private path"))
        obj, _, _ = service(telemetry=sink)
        self.assertEqual(obj.classify_tool_risk("read", True).fallback_reason, "telemetry_error")

    def test_mutating_advice_does_not_mutate_fallback_policy(self):
        obj, adapter, _ = service(manifest(enabled=False))
        advice = obj.classify_tool_risk("read", True)
        advice.answers["risk"]["score"] = 0
        self.assertEqual(obj.classify_tool_risk("read", True).answers["risk"]["score"], 2)

    def test_jsonl_appends_only_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jev.jsonl"
            obj, _, _ = service(telemetry=JevJsonlTelemetry(path))
            obj.classify_tool_risk("read", True)
            obj.classify_tool_risk("write", True)
            lines = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(lines), 2)
            self.assertNotIn("state", lines[0])


class EnvironmentTests(unittest.TestCase):
    @staticmethod
    def verification(valid=True):
        return Verification(TerminalState.VERIFIED, valid, True, None, None, None, False, False, True)

    def test_advisory_tool_answer_cannot_grant_or_revoke_permission(self):
        for allow in (0.0, 1.0):
            obj, adapter, events = service(result=response("tool-call-guard", allow_tool_call=allow))
            tool = Mock(return_value={"ok": True})
            env = GibsonEnv({"read": tool, "forbidden": tool}, lambda *_: self.verification(), decisions=obj)
            env.reset(Task("task", ".", "issue with secret and hidden answer", ("read",)))
            observation, _ = env.step(Action("forbidden", {"secret": "credential"}))
            self.assertEqual(observation.tool_result["error"], "PERMISSION_DENIED")
            tool.assert_not_called()
            env.step(Action("read", {"secret": "credential"}))
            tool.assert_called_once()
            self.assertNotIn("credential", json.dumps(adapter.request.call_args_list, default=str))
            self.assertNotIn("issue with secret", json.dumps(adapter.request.call_args_list, default=str))
            self.assertEqual(env.verify().terminal_state, TerminalState.VERIFIED)
            self.assertFalse(any(e["kind"] == "jev_decision" for e in env.events))

    def test_jev_cannot_award_verified_or_change_evidence_gate(self):
        obj, _, _ = service()
        env = GibsonEnv({"read": lambda _: {}}, lambda *_: self.verification(False), decisions=obj)
        env.reset(Task("task", ".", "issue", ("read",)))
        env.step(Action("read", {}))
        with self.assertRaisesRegex(ValueError, "unsupported VERIFIED"):
            env.verify()

    def test_disabled_hook_preserves_original_trace_and_verifier_inputs(self):
        verifier = Mock(return_value=self.verification())
        task = Task("task", ".", "issue", ("read",))
        obj, adapter, _ = service(manifest(enabled=False))
        envs = [GibsonEnv({"read": lambda _: {"ok": True}}, verifier, decisions=d) for d in (None, obj)]
        for env in envs:
            env.reset(task)
            env.step(Action("read", {}))
            env.verify()
        self.assertEqual(envs[0].events, envs[1].events)
        self.assertEqual(verifier.call_args_list[0], verifier.call_args_list[1])
        adapter.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
