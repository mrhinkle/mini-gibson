from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"

Transport = Callable[[str, dict[str, str], bytes, float], dict[str, Any]]


@dataclass(frozen=True)
class JevConfig:
    enabled: bool = False
    endpoint: str = DEFAULT_ENDPOINT
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 3.0
    min_confidence: float = 0.80

    @classmethod
    def from_env(cls) -> "JevConfig":
        enabled = os.getenv("MINI_GIBSON_JEV_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        return cls(
            enabled=enabled,
            endpoint=os.getenv("MINI_GIBSON_JEV_ENDPOINT", DEFAULT_ENDPOINT),
            model=os.getenv("MINI_GIBSON_JEV_MODEL", DEFAULT_MODEL),
            timeout_seconds=float(os.getenv("MINI_GIBSON_JEV_TIMEOUT_SECONDS", "3")),
            min_confidence=float(os.getenv("MINI_GIBSON_JEV_MIN_CONFIDENCE", "0.80")),
        )


@dataclass(frozen=True)
class JevDecision:
    status: str
    answers: dict[str, Any]
    request_hash: str
    model: str | None
    latency_ms: float
    question_set_version: str
    confidence: float | None = None
    requires_fallback: bool = False
    error: str | None = None


def _default_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _stable_hash(state: Any, questions: dict[str, Any], version: str) -> str:
    payload = json.dumps(
        {"state": state, "questions": questions, "question_set_version": version},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _extract_confidence(answers: dict[str, Any]) -> float | None:
    candidates: list[float] = []
    for answer in answers.values():
        if not isinstance(answer, dict):
            continue
        for key in ("confidence", "probability"):
            value = answer.get(key)
            if isinstance(value, (int, float)):
                candidates.append(float(value))
        probs = answer.get("probabilities")
        if isinstance(probs, dict):
            candidates.extend(
                float(v) for v in probs.values() if isinstance(v, (int, float))
            )
    return min(candidates) if candidates else None


class JevClient:
    """Optional TypeSafe Jev client.

    Jev is a bounded decision service. It must not generate code, award VERIFIED,
    or replace deterministic Evidence Gate logic.
    """

    def __init__(
        self,
        config: JevConfig | None = None,
        *,
        api_key: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.config = config or JevConfig.from_env()
        self.api_key = api_key if api_key is not None else os.getenv("TYPESAFE_API_KEY")
        self._transport = transport or _default_transport

    def decide(
        self,
        *,
        state: Any,
        questions: dict[str, Any],
        question_set_version: str,
    ) -> JevDecision:
        request_hash = _stable_hash(state, questions, question_set_version)

        if not self.config.enabled:
            return JevDecision(
                status="disabled",
                answers={},
                request_hash=request_hash,
                model=None,
                latency_ms=0.0,
                question_set_version=question_set_version,
                requires_fallback=True,
            )

        if not self.api_key:
            return JevDecision(
                status="configuration_error",
                answers={},
                request_hash=request_hash,
                model=self.config.model,
                latency_ms=0.0,
                question_set_version=question_set_version,
                requires_fallback=True,
                error="TYPESAFE_API_KEY is required when Jev is enabled",
            )

        payload = json.dumps(
            {
                "state": state,
                "model": self.config.model,
                "questions": questions,
            },
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        try:
            raw = self._transport(
                self.config.endpoint,
                headers,
                payload,
                self.config.timeout_seconds,
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return JevDecision(
                status="error",
                answers={},
                request_hash=request_hash,
                model=self.config.model,
                latency_ms=(time.perf_counter() - started) * 1000,
                question_set_version=question_set_version,
                requires_fallback=True,
                error=f"{type(exc).__name__}: {exc}",
            )

        latency_ms = (time.perf_counter() - started) * 1000
        answers = raw.get("answers")
        if not isinstance(answers, dict):
            return JevDecision(
                status="invalid_response",
                answers={},
                request_hash=request_hash,
                model=str(raw.get("model") or self.config.model),
                latency_ms=latency_ms,
                question_set_version=question_set_version,
                requires_fallback=True,
                error="response missing answers object",
            )

        confidence = _extract_confidence(answers)
        low_confidence = (
            confidence is not None and confidence < self.config.min_confidence
        )
        return JevDecision(
            status="ok",
            answers=answers,
            request_hash=request_hash,
            model=str(raw.get("model") or self.config.model),
            latency_ms=latency_ms,
            question_set_version=question_set_version,
            confidence=confidence,
            requires_fallback=low_confidence,
        )
