"""Fail-closed validation of the optional Jev extension, not a design-freeze gate."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from adapters.jev import ENDPOINT, QUESTIONS, QUESTION_SET_VERSION, JevConfig, canonical_json


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def policy_fingerprint(config: JevConfig) -> str:
    return digest({"config": asdict(config), "endpoint": ENDPOINT, "questions": QUESTIONS,
                   "question_set_version": QUESTION_SET_VERSION,
                   "state_projection": "mini-gibson-jev-state/v1", "fallback_policy": "advisory-human/v1"})


def mapping(value: object, name: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True)
class DecisionPolicy:
    config: JevConfig
    scored: bool
    policy_sha256: str


def validate_manifest(manifest: object, arm_id: str | None = None) -> DecisionPolicy:
    manifest = mapping(manifest, "manifest")
    run = mapping(manifest.get("run", {}), "run")
    scored = run.get("scored", True)  # Missing context is treated as scored.
    if type(scored) is not bool:
        raise ValueError("run.scored must be a boolean")
    integrations = mapping(manifest.get("integrations", {}), "integrations")
    raw = mapping(integrations.get("jev", {}), "integrations.jev")
    root = JevConfig.parse(raw)
    comparison = mapping(manifest.get("comparison", {}), "comparison")
    arms = comparison.get("arms", [])
    if not isinstance(arms, list):
        raise ValueError("comparison.arms must be a list")
    configs = {}
    for arm in arms:
        arm = mapping(arm, "arm")
        name = arm.get("id")
        if not isinstance(name, str) or not name or name in configs:
            raise ValueError("comparison arms need unique nonempty IDs")
        overrides = mapping(arm.get("integrations", {}), "arm.integrations")
        jev = mapping(overrides.get("jev", {}), "arm.integrations.jev")
        configs[name] = JevConfig.parse({**raw, **jev})
    if arm_id is not None and arm_id not in configs:
        raise ValueError("unknown comparison arm")
    candidates = [root, *configs.values()]
    if scored and any(c.enabled and c.scored_loop == "identical_across_all_arms" for c in candidates):
        if len(configs) < 2 or arm_id is None:
            raise ValueError("scored Jev requires a complete comparison and an explicit arm ID")
        # Include root defaults: a one-arm override cannot quietly enable Jev.
        if any(c != root for c in candidates):
            raise ValueError("Jev policy must be identical across all compared arms")
        if comparison.get("jev_policy_sha256") != policy_fingerprint(root):
            raise ValueError("freeze comparison.jev_policy_sha256 before scored Jev use")
    selected = configs[arm_id] if arm_id is not None else root
    return DecisionPolicy(selected, scored, policy_fingerprint(selected))


def load_manifest(path: str | Path, arm_id: str | None = None) -> DecisionPolicy:
    import yaml
    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def unique_mapping(loader, node, deep=False):
        pairs = loader.construct_pairs(node, deep=deep)
        result = {}
        for key, value in pairs:
            try:
                if key in result:
                    raise ValueError("duplicate manifest key")
                result[key] = value
            except TypeError:
                raise ValueError("invalid manifest mapping key") from None
        return result

    UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
    with Path(path).open(encoding="utf-8") as source:
        try:
            manifest = yaml.load(source, Loader=UniqueKeyLoader)
        except yaml.YAMLError:
            raise ValueError("invalid manifest YAML") from None
    return validate_manifest(manifest, arm_id)
