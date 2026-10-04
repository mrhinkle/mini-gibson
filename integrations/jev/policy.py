from __future__ import annotations

from typing import Any

ALLOWED_CAUSAL_POLICIES = {"outside_scored_loop", "identical_across_arms"}


def validate_causal_use(
    *,
    jev_enabled: bool,
    causal_policy: str,
    arm_configs: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Fail closed when Jev would become an unregistered treatment variable."""
    if not jev_enabled:
        return
    if causal_policy not in ALLOWED_CAUSAL_POLICIES:
        raise ValueError(
            "Jev must be outside the scored loop or identically configured across arms"
        )
    if causal_policy == "outside_scored_loop":
        return

    configs = arm_configs or {}
    if len(configs) < 2:
        raise ValueError("identical_across_arms requires at least two arm configs")

    normalized = [_normalize(config) for _, config in sorted(configs.items())]
    if any(item != normalized[0] for item in normalized[1:]):
        raise ValueError("Jev configuration differs across experimental arms")


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value
