from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import JevClient, JevDecision


@dataclass(frozen=True)
class DecisionOutcome:
    value: str
    source: str
    telemetry: JevDecision


class JevDecisionService:
    """Bounded Mini Gibson decisions with deterministic safe fallbacks."""

    def __init__(self, client: JevClient) -> None:
        self.client = client

    def supervisor_action(self, state: dict[str, Any]) -> DecisionOutcome:
        return self._decide_choice(
            state=state,
            version="supervisor-v1",
            name="action",
            instructions="Choose the safest next supervisor action.",
            options=["continue", "retry_infrastructure", "stop", "human_escalation"],
            fallback="human_escalation",
        )

    def tool_risk(self, state: dict[str, Any]) -> DecisionOutcome:
        return self._decide_choice(
            state=state,
            version="tool-risk-v1",
            name="risk",
            instructions="Classify the operational risk of the proposed tool call.",
            options=["low", "medium", "high", "human_review"],
            fallback="human_review",
        )

    def anomaly_triage(self, state: dict[str, Any]) -> DecisionOutcome:
        return self._decide_choice(
            state=state,
            version="anomaly-v1",
            name="anomaly_class",
            instructions="Classify this run anomaly.",
            options=[
                "expected_task_failure",
                "infrastructure_failure",
                "telemetry_corruption",
                "requires_human_review",
            ],
            fallback="requires_human_review",
        )

    def _decide_choice(
        self,
        *,
        state: dict[str, Any],
        version: str,
        name: str,
        instructions: str,
        options: list[str],
        fallback: str,
    ) -> DecisionOutcome:
        decision = self.client.decide(
            state=state,
            question_set_version=version,
            questions={
                name: {
                    "type": "choice",
                    "instructions": instructions,
                    "options": options,
                }
            },
        )
        value = self._choice(decision, name, fallback)
        source = "fallback" if decision.requires_fallback or decision.status != "ok" else "jev"
        return DecisionOutcome(value=value, source=source, telemetry=decision)

    @staticmethod
    def _choice(decision: JevDecision, name: str, fallback: str) -> str:
        if decision.requires_fallback or decision.status != "ok":
            return fallback
        answer = decision.answers.get(name)
        if not isinstance(answer, dict):
            return fallback
        for key in ("choice", "value", "answer"):
            value = answer.get(key)
            if isinstance(value, str):
                return value
        return fallback
