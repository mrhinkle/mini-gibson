# Optional Jev decision service

Jev provides typed operational advice through the official TypeSafe decision API. It is disabled by default and remains outside Mini Gibson's critical path. Nemotron remains the coding model; GibsonEnv's deterministic Evidence Gate remains the only authority for `VERIFIED`.

## Implemented boundary

`adapters/jev.py` makes one `POST https://api.typesafe.ai/v1/systemone` request with a version-pinned model (`jev-1.13.0` by default). Credentials are read only from the process environment variable `TYPESAFE_API_KEY`. No key, credential file, custom endpoint, or authentication header belongs in a manifest. Redirects are refused, the response is bounded to 64 KiB, and there are no automatic retries.

`experiment.decisions.DecisionService` accepts a manifest dictionary, an optional comparison `arm_id`, and a telemetry callable. Enabled services require telemetry. Numeric timeout/confidence values normalize before hashing so equivalent numeric representations share a policy hash. An adapter can be injected for deterministic tests. `experiment.manifest.load_manifest(path, arm_id=None)` loads YAML and validates the Jev extension; it is not a complete experiment validator or a replacement for the pending design freeze.

| Hook | Accepted operational state | Authority |
| --- | --- | --- |
| `supervisor_advice` | Infrastructure health, failure kind, execution-start flag, declared infrastructure-retry eligibility, retry count | Advisory action, human-attention flag, risk score |
| `classify_tool_risk` | Declared tool identity and existing permission flag | Advisory permission/risk metadata |
| `triage_anomaly` | Recorded terminal state, failure kind, tool-error count | Advisory anomaly category |
| `routing_advice` | Current agent identity and infrastructure health | Operator routing advice; always excluded in scored mode |

Each hook accepts typed, bounded metadata. It does not accept raw source code, tool arguments, prompts, issue text, hidden benchmark answers, or credentials. Tool names outside the allowed identifier syntax become `unrecognized_tool`; undeclared tool requests in GibsonEnv are represented as `undeclared_tool`.

`GibsonEnv(tools, verifier, decisions=service)` calls the tool-risk hook before its existing permission check. The returned advice is recorded through telemetry only: it cannot grant, revoke, or change permission, alter the observation/action trace, execute a retry, or change verification. Supervisor and benchmark runners do not yet exist in this foundation; their exported hooks are ready for their owners to call. This change does not claim a complete supervisor, benchmark runner, or live TypeSafe deployment.

Jev must never generate code, replace Nemotron, award `VERIFIED`, replace or alter Evidence Gate logic, inspect hidden answers, change tool permissions, decide adapter promotion, change recorded scores, or rerun failed engineering tasks until they pass. Caller code must preserve these boundaries when future runners consume advice.

## Configuration

Only these fields are accepted under an experiment's `integrations.jev`; omission uses the defaults below. The standalone `integrations/jev.yaml` file documents the contract and ownership, rather than being loaded as an experiment configuration.

```yaml
run:
  scored: true
integrations:
  jev:
    enabled: false
    model: jev-1.13.0
    timeout_seconds: 3.0
    min_confidence: 0.8
    scored_loop: excluded_from_scored_loop
```

`timeout_seconds` must be finite and between 0.1 and 30; it is the transport's socket/per-request timeout, not a guaranteed total wall-clock deadline. `min_confidence` must be finite and between 0.5 and 1. Moving model aliases are rejected. Unknown fields are rejected, including manifest credentials. YAML loading rejects duplicate keys and invalid syntax without echoing manifest contents. This implementation accepts a syntactically pinned `jev-x.y.z` model; only the default version was checked against the official documentation. No live authenticated API call was performed.

For an explicit noncausal operator session, set `run.scored: false`. Leaving `run.scored` out means **scored**, so missing context cannot silently permit remote advice. Do not enable the integration or provision credentials as part of a benchmark freeze without the owner-approved operational and credential setup.

## Causal fairness

The default `excluded_from_scored_loop` policy prevents all remote Jev calls whenever `run.scored` is true. Hooks return deterministic fallback metadata. With this policy, post-outcome anomaly investigation uses a separate, explicitly noncausal operator context; it must preserve the immutable result and cannot rescore the trial.

The optional `identical_across_all_arms` policy permits supervisor, tool-risk, and anomaly advice only when manifest validation proves a frozen identical configuration:

1. Declare every compared arm under `comparison.arms`, with unique nonempty IDs and at least two arms. An A/B/C comparison declares all three.
2. Supply the executing arm explicitly to `DecisionService(..., arm_id="A", ...)` or `load_manifest(..., arm_id="A")`.
3. Keep each arm's effective Jev configuration equal to the root configuration. Arm overrides are merged with root settings; a difference in enablement, model, timeout, confidence threshold, or loop policy is rejected.
4. Set `comparison.jev_policy_sha256` to `policy_fingerprint(JevConfig.parse(manifest["integrations"]["jev"]))` before the run. The fingerprint includes effective configuration, endpoint, question definitions/version, state-projection version, and fallback-policy version.

For example, the comparison portion of an otherwise complete, owner-frozen manifest is:

```yaml
comparison:
  arms:
    - id: A
    - id: B
    - id: C
  jev_policy_sha256: REPLACE_WITH_COMPUTED_POLICY_FINGERPRINT
```

The placeholder is deliberately invalid for enabled scored Jev. The validator rejects missing/stale fingerprints, incomplete comparisons, missing or unknown arm IDs, and per-arm policy changes. Operator routing remains excluded even in identical mode. A change to the in-memory question/policy fingerprint after validation causes deterministic fallback before any remote request. The validator can check the arms declared in a manifest; the future runner must ensure that the declared list is the actual comparison, use the same call sites/state projection in each arm, account for Jev latency consistently, and retain the frozen manifest with the run receipt. Equal policy does not guarantee equal stochastic answers or live service availability.

## Typed answers and deterministic fallback

Question set `mini-gibson-jev/v1` uses TypeSafe `choice`, `noul`, and `score` primitives. Choice answers must select a declared option; choice/score probability maps must contain exactly the expected keys, have finite probabilities in [0, 1], and sum to one. Scores may be fractional over the rubric's numeric levels (`0=low`, `1=medium`, `2=high`). A mismatched model, malformed response, network/HTTP error, missing credentials, or low confidence produces fallback advice.

Choice and score use provider confidence. Noul supplies a yes probability rather than a confidence field, so this implementation derives its local certainty as `abs(2 * p - 1)`. The minimum certainty across the question set must meet `min_confidence`. This local rule is logged explicitly and is not described as a provider confidence formula.

| Decision point | Deterministic fallback |
| --- | --- |
| Supervisor | `human_escalation`, `needs_human=1`, high risk |
| Tool risk | `allow_tool_call=0`, high risk; existing deterministic permissions still apply |
| Benchmark anomaly | `requires_human_review` |
| Operator routing | `human` |

A supervisor recommendation to retry is rejected unless the supplied state declares an unhealthy infrastructure failure before execution and an already-authorized infrastructure retry. This guard does not itself authorize or perform a retry. An unpermitted tool remains unpermitted. A failing telemetry sink prevents remote advice from being returned and yields `telemetry_error` fallback.

## Telemetry

A callable receives one `jev_decision` event per hook invocation, including disabled/excluded/fallback invocations. `telemetry.jev.JevJsonlTelemetry(path)` appends newline-delimited JSON to a run-owned file; the caller creates the parent directory and associates the artifact with the immutable run/trial receipt. The sink never truncates an existing receipt. Run locking, durable fsync, and completed-trial immutability remain runner responsibilities.

Events contain decision point, question-set version, pinned model, policy/state/request SHA-256 hashes, validated typed provider answers, effective answers, confidence, the local Noul certainty policy, elapsed latency in milliseconds, source, fallback reason, a bounded safe error code, sanitized response model, and integer input/output usage counts when supplied. They omit raw state, request/response bodies, headers, credentials, tool arguments, source, and issue text. A telemetry failure cannot be reliably recorded to the failed sink; callers can observe it in the returned `Advice.fallback_reason`.

Hashes support receipt correlation and policy checks; they are not a substitute for access control or anonymization. John consumes the metadata after the immutable outcome, retains failed/unavailable receipts, and reports latency/fallback/error counts without turning advice into a benchmark score or a verified result.

## Ownership and acceptance

Mark/Codex owns adapter/configuration, manifest fairness validation, telemetry production, runtime hook wiring, and runtime tests. John/Grok owns future anomaly-hook calls from redacted recorded summaries and report consumption/observability after immutable results. Claude independently reviews the exact head and coordinates changes to shared question, policy, and artifact contracts. Jev remains a cuttable optional extension; broader draft/design/benchmark freeze gates still apply.

Use Python >=3.11 and the pinned PyYAML dependency from `pyproject.toml`:

```sh
python -m pip install -e .
python -m experiment.validate experiment.example.yaml
python -m unittest discover -v
```

The validation command checks only the Jev extension and prints enablement, scoring context, loop policy and the computed policy hash; `--arm A` selects a declared arm. It does not certify the full experiment freeze.

Acceptance requires deterministic tests proving: disabled/excluded modes make no remote call; requests use the official endpoint/environment-only credential boundary; all primitive shapes and low-confidence/error fallbacks work; unequal or unfrozen scored policies fail closed; telemetry includes safe metadata/hashes; Jev advice cannot change permission, verification, scores, or promotion; and GibsonEnv permission/verification invariants remain green. Mocked API fixtures test the documented contract, not live account/model availability. Future supervisor/benchmark integration needs its own tests when those runners exist.

## Official references

The transport and type contract follow TypeSafe's [API reference](https://docs.typesafe.ai/api), [pinned model documentation](https://docs.typesafe.ai/models), [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [Noul](https://docs.typesafe.ai/primitives/noul), and [confidence documentation](https://docs.typesafe.ai/confidence), checked October 4, 2026.
