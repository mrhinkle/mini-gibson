"""Official TypeSafe REST transport; no generation or execution authority."""
from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
QUESTION_SET_VERSION = "mini-gibson-jev/v1"

QUESTIONS = {
    "supervisor-escalation": {
        "action": {"type": "choice", "instructions": "Recommend the next supervisor action within the declared retry policy.",
                   "criteria": {"continue": "Proceed within the existing budget.", "retry_infrastructure": "Retry an eligible infrastructure failure before task execution.",
                                "stop": "Stop this run without changing its score.", "human_escalation": "Ask the human operator for a decision."}},
        "needs_human": {"type": "noul", "instructions": "Does this operational state need human attention?"},
        "run_risk": {"type": "score", "instructions": "Rate operational risk.", "criteria": ["low", "medium", "high"]},
    },
    "tool-call-guard": {
        "allow_tool_call": {"type": "noul", "instructions": "Is this declared tool call low risk under its existing permission? This answer cannot grant permission."},
        "risk": {"type": "score", "instructions": "Rate risk using only the supplied tool identity and permission metadata.", "criteria": ["low", "medium", "high"]},
    },
    "benchmark-anomaly-triage": {
        "anomaly_class": {"type": "choice", "instructions": "Classify this redacted result summary for human review; never change the recorded result.",
                          "criteria": {"expected_task_failure": "Task failure recorded normally.", "infrastructure_failure": "Infrastructure problem requiring investigation.",
                                       "telemetry_corruption": "Telemetry appears incomplete or inconsistent.", "requires_human_review": "The summary needs human review."}},
    },
    "model-or-agent-routing": {
        "route": {"type": "choice", "instructions": "Suggest an operator to receive this escalation. Never switch a model or promote an adapter.",
                  "criteria": {"hermes": "Hermes operator", "codex": "Codex operator", "claude_code": "Claude Code operator", "grok": "Grok operator", "human": "Human owner"}},
    },
}


class JevError(Exception):
    """Safe, bounded error code; never includes headers, state or response text."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def probability(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise JevError("invalid_response")
    return float(value)


@dataclass(frozen=True)
class JevConfig:
    enabled: bool = False
    model: str = "jev-1.13.0"
    timeout_seconds: float = 3.0
    min_confidence: float = 0.8
    scored_loop: str = "excluded_from_scored_loop"

    @classmethod
    def parse(cls, value: object) -> JevConfig:
        if not isinstance(value, Mapping):
            raise ValueError("integrations.jev must be a mapping")
        if set(value) - {"enabled", "model", "timeout_seconds", "min_confidence", "scored_loop"}:
            raise ValueError("unknown Jev configuration field; credentials belong only in TYPESAFE_API_KEY")
        config = cls(**value)
        if type(config.enabled) is not bool:
            raise ValueError("Jev enabled must be a boolean")
        # Version identifiers only: moving aliases are never accepted.
        parts = config.model.removeprefix("jev-").split(".") if isinstance(config.model, str) else []
        if not isinstance(config.model, str) or not config.model.startswith("jev-") or len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError("Jev model must be pinned, for example jev-1.13.0")
        for field, low, high in (("timeout_seconds", 0.1, 30), ("min_confidence", 0.5, 1)):
            number = getattr(config, field)
            if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
                raise ValueError(f"invalid Jev {field}")
        if config.scored_loop not in ("excluded_from_scored_loop", "identical_across_all_arms"):
            raise ValueError("invalid Jev scored_loop policy")
        return cls(config.enabled, config.model, float(config.timeout_seconds),
                   float(config.min_confidence), config.scored_loop)

    def payload(self, point: str, state: dict) -> dict:
        return {"model": self.model, "state": state, "questions": QUESTIONS[point]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise JevError("redirect_refused")


class JevAdapter:
    """Single bounded POST, fixed official HTTPS origin, environment-only auth."""

    def request(self, payload: dict, timeout_seconds: float) -> dict:
        key = os.environ.get("TYPESAFE_API_KEY", "")
        if not key.strip():
            raise JevError("missing_credentials")
        try:
            request = Request(ENDPOINT, data=canonical_json(payload).encode(), method="POST",
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            with build_opener(NoRedirect()).open(request, timeout=timeout_seconds) as response:
                body = response.read(65537)
                if len(body) > 65536:
                    raise JevError("response_too_large")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise JevError("invalid_response")
            return value
        except HTTPError as exc:
            exc.close()
            raise JevError(f"http_{exc.code}") from None
        except (TimeoutError, URLError):
            raise JevError("transport_error") from None
        except (ValueError, UnicodeError):
            raise JevError("invalid_response") from None


def typed_answers(response: object, point: str, model: str) -> tuple[dict, float]:
    if not isinstance(response, dict) or response.get("model") != model:
        raise JevError("model_mismatch")
    answers = response.get("answers")
    questions = QUESTIONS[point]
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise JevError("invalid_response")
    clean, confidences = {}, []
    for name, question in questions.items():
        answer = answers[name]
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise JevError("invalid_response")
        kind = question["type"]
        if kind == "noul":
            p = probability(answer.get("noul"))
            clean[name] = {"type": kind, "noul": p}
            confidences.append(abs(2 * p - 1))
            continue
        confidence = probability(answer.get("confidence"))
        distribution = answer.get("probabilities")
        options = list(question["criteria"]) if kind == "choice" else [str(i) for i in range(len(question["criteria"]))]
        if not isinstance(distribution, dict) or set(distribution) != set(options):
            raise JevError("invalid_response")
        probs = {option: probability(distribution[option]) for option in options}
        if not math.isclose(sum(probs.values()), 1, abs_tol=1e-5):
            raise JevError("invalid_response")
        value = answer.get(kind)
        if kind == "choice":
            if value not in options or probs[value] < max(probs.values()):
                raise JevError("invalid_response")
        elif type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= len(options) - 1:
            raise JevError("invalid_response")
        elif not math.isclose(value, sum(int(i) * p for i, p in probs.items()), abs_tol=1e-5):
            raise JevError("invalid_response")
        clean[name] = {"type": kind, kind: value, "confidence": confidence, "probabilities": probs}
        confidences.append(confidence)
    return clean, min(confidences)
