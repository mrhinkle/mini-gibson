import json
import unittest

from integrations.jev import JevClient, JevConfig, JevDecisionService, validate_causal_use


class JevIntegrationTests(unittest.TestCase):
    def test_disabled_client_never_calls_transport(self):
        called = False

        def transport(*args):
            nonlocal called
            called = True
            return {}

        client = JevClient(JevConfig(enabled=False), api_key=None, transport=transport)
        result = client.decide(
            state={"x": 1},
            questions={"q": {"type": "noul", "instructions": "ok?"}},
            question_set_version="v1",
        )
        self.assertEqual(result.status, "disabled")
        self.assertTrue(result.requires_fallback)
        self.assertFalse(called)

    def test_missing_key_fails_closed(self):
        client = JevClient(JevConfig(enabled=True), api_key=None, transport=lambda *a: {})
        result = client.decide(
            state="x",
            questions={"q": {"type": "noul", "instructions": "ok?"}},
            question_set_version="v1",
        )
        self.assertEqual(result.status, "configuration_error")
        self.assertTrue(result.requires_fallback)

    def test_supervisor_decision_uses_typed_choice(self):
        def transport(url, headers, body, timeout):
            payload = json.loads(body)
            self.assertEqual(payload["model"], "jev-latest")
            return {
                "model": "jev-latest",
                "answers": {"action": {"choice": "continue", "probability": 0.95}},
            }

        client = JevClient(
            JevConfig(enabled=True, min_confidence=0.8),
            api_key="test-only",
            transport=transport,
        )
        outcome = JevDecisionService(client).supervisor_action({"healthy": True})
        self.assertEqual(outcome.value, "continue")
        self.assertEqual(outcome.source, "jev")
        self.assertFalse(outcome.telemetry.requires_fallback)

    def test_low_confidence_uses_safe_fallback(self):
        def transport(*args):
            return {"answers": {"risk": {"choice": "low", "probability": 0.51}}}

        client = JevClient(
            JevConfig(enabled=True, min_confidence=0.8),
            api_key="test-only",
            transport=transport,
        )
        outcome = JevDecisionService(client).tool_risk({"tool": "run_command"})
        self.assertEqual(outcome.value, "human_review")
        self.assertEqual(outcome.source, "fallback")

    def test_causal_policy_rejects_arm_differences(self):
        with self.assertRaises(ValueError):
            validate_causal_use(
                jev_enabled=True,
                causal_policy="identical_across_arms",
                arm_configs={
                    "A": {"model": "jev-latest", "min_confidence": 0.8},
                    "B": {"model": "jev-latest", "min_confidence": 0.9},
                },
            )

    def test_causal_policy_accepts_identical_arms(self):
        validate_causal_use(
            jev_enabled=True,
            causal_policy="identical_across_arms",
            arm_configs={
                "A": {"model": "jev-latest", "min_confidence": 0.8},
                "B": {"model": "jev-latest", "min_confidence": 0.8},
            },
        )


if __name__ == "__main__":
    unittest.main()
