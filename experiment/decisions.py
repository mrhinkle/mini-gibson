"""Advisory hooks with minimal metadata state; never execute returned decisions."""
from __future__ import annotations

import re
import time
import copy
from collections.abc import Callable
from dataclasses import dataclass

from adapters.jev import QUESTION_SET_VERSION, JevAdapter, JevError, typed_answers
from .manifest import digest, policy_fingerprint, validate_manifest

FALLBACKS = {
    "supervisor-escalation": {"action": {"type": "choice", "choice": "human_escalation"},
                              "needs_human": {"type": "noul", "noul": 1.0}, "run_risk": {"type": "score", "score": 2.0}},
    "tool-call-guard": {"allow_tool_call": {"type": "noul", "noul": 0.0}, "risk": {"type": "score", "score": 2.0}},
    "benchmark-anomaly-triage": {"anomaly_class": {"type": "choice", "choice": "requires_human_review"}},
    "model-or-agent-routing": {"route": {"type": "choice", "choice": "human"}},
}


@dataclass(frozen=True)
class Advice:
    answers: dict
    source: str
    fallback_reason: str | None


class DecisionService:
    def __init__(self, manifest: dict, *, arm_id: str | None = None,
                 telemetry: Callable[[dict], None] | None = None, adapter: JevAdapter | None = None):
        self.policy = validate_manifest(manifest, arm_id)
        if self.policy.config.enabled and telemetry is None:
            raise ValueError("enabled Jev requires a telemetry sink")
        self.telemetry = telemetry
        self.adapter = adapter or JevAdapter()

    def supervisor_advice(self, *, infrastructure_healthy: bool, failure_kind: str,
                          execution_started: bool, infrastructure_retry_allowed: bool, retry_count: int) -> Advice:
        self._booleans(infrastructure_healthy, execution_started, infrastructure_retry_allowed)
        self._failure(failure_kind)
        self._count(retry_count)
        return self._decide("supervisor-escalation", {
            "infrastructure_healthy": infrastructure_healthy, "failure_kind": failure_kind,
            "execution_started": execution_started, "infrastructure_retry_allowed": infrastructure_retry_allowed,
            "retry_count": retry_count,
        })

    def classify_tool_risk(self, tool: str, permission_granted: bool) -> Advice:
        self._booleans(permission_granted)
        # Tool arguments, source code, prompts, task issues, credentials and hidden answers never enter state.
        if not isinstance(tool, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", tool):
            tool = "unrecognized_tool"  # Invalid free-form names must not become an exfiltration path.
        return self._decide("tool-call-guard", {"tool": tool, "permission_granted": permission_granted})

    def triage_anomaly(self, *, terminal_state: str, failure_kind: str, tool_error_count: int) -> Advice:
        if terminal_state not in {"VERIFIED", "PARTIALLY_VERIFIED", "FAILED", "ABORTED"}:
            raise ValueError("invalid terminal state")
        self._failure(failure_kind)
        self._count(tool_error_count)
        return self._decide("benchmark-anomaly-triage", {
            "terminal_state": terminal_state, "failure_kind": failure_kind, "tool_error_count": tool_error_count,
        })

    def routing_advice(self, *, current_agent: str, infrastructure_healthy: bool) -> Advice:
        self._booleans(infrastructure_healthy)
        if current_agent not in {"hermes", "codex", "claude_code", "grok", "human"}:
            raise ValueError("unknown current agent")
        return self._decide("model-or-agent-routing", {
            "current_agent": current_agent, "infrastructure_healthy": infrastructure_healthy,
        })

    @staticmethod
    def _booleans(*values):
        if any(type(v) is not bool for v in values):
            raise ValueError("operational flags must be booleans")

    @staticmethod
    def _count(value):
        if type(value) is not int or not 0 <= value <= 1000000:
            raise ValueError("invalid operational counter")

    @staticmethod
    def _failure(value):
        if value not in {"none", "task", "infrastructure", "telemetry"}:
            raise ValueError("invalid failure kind")

    def _decide(self, point: str, state: dict) -> Advice:
        config = self.policy.config
        payload = config.payload(point, state)
        started = time.monotonic()
        provider_answers, confidence, error, reason = {}, None, None, None
        response_model, usage = None, None
        if policy_fingerprint(config) != self.policy.policy_sha256:
            reason = "policy_changed"
        elif not config.enabled:
            reason = "disabled"
        elif self.policy.scored and (config.scored_loop == "excluded_from_scored_loop" or point == "model-or-agent-routing"):
            reason = "scored_loop_excluded"
        else:
            try:
                response = self.adapter.request(payload, config.timeout_seconds)
                candidate = response.get("model") if isinstance(response, dict) else None
                if isinstance(candidate, str) and re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", candidate):
                    response_model = candidate
                candidate = response.get("usage") if isinstance(response, dict) else None
                if isinstance(candidate, dict) and all(type(candidate.get(k)) is int and candidate[k] >= 0
                                                       for k in ("input_tokens", "output_tokens")):
                    usage = {k: candidate[k] for k in ("input_tokens", "output_tokens")}
                provider_answers, confidence = typed_answers(response, point, config.model)
                if confidence < config.min_confidence:
                    reason = "low_confidence"
                elif point == "supervisor-escalation" and provider_answers["action"]["choice"] == "retry_infrastructure":
                    if not (state["failure_kind"] == "infrastructure" and not state["execution_started"]
                            and not state["infrastructure_healthy"] and state["infrastructure_retry_allowed"]):
                        reason = "retry_not_authorized"
                elif point == "tool-call-guard" and not state["permission_granted"]:
                    reason = "permission_denied"
            except JevError as exc:
                # JevError contract contains only a safe code; custom adapters still cannot leak exception text.
                code = str(exc)
                safe_codes = {"missing_credentials", "redirect_refused", "transport_error", "invalid_response",
                              "response_too_large", "model_mismatch"}
                error = code if code in safe_codes or re.fullmatch(r"http_[0-9]{3}", code) else "adapter_error"
                reason = "unavailable"
            except Exception:
                error, reason = "adapter_error", "unavailable"
        effective = copy.deepcopy(FALLBACKS[point] if reason else provider_answers)
        event = {"kind": "jev_decision", "decision_point": point, "question_set_version": QUESTION_SET_VERSION,
                 "model": config.model, "policy_sha256": self.policy.policy_sha256,
                 "response_model": response_model, "usage": usage,
                 "state_sha256": digest(state), "request_sha256": digest(payload),
                 "typed_answers": provider_answers, "effective_answers": effective,
                 "confidence": confidence, "noul_confidence_policy": "local_abs_2p_minus_1",
                 "latency_ms": round((time.monotonic() - started) * 1000, 3),
                 "fallback": reason, "error": error, "source": "fallback" if reason else "jev"}
        if self.telemetry is not None:
            try:
                self.telemetry(event)
            except Exception:
                # Unlogged remote advice must never be consumed; do not leak sink exception text.
                return Advice(copy.deepcopy(FALLBACKS[point]), "fallback", "telemetry_error")
        return Advice(effective, event["source"], reason)
