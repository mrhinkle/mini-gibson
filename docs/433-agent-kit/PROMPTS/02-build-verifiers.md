# Prompt — Phase 2 Build verifiers

## Codex CLI

```text
Phase 2: strengthen verification for #433 observational tasks.

Scope:
- For kind=investigate fixtures, add expected.json (path + value the agent must find) and a small verifier that scores the completion claim / report file WITHOUT trusting the word VERIFIED alone.
- Keep unittest/node verify_cmd for code tasks.
- Update observational_runner.independent_verify (or a sibling script) to call investigate keys.
- Do not spend OpenRouter budget in this phase.

Files to touch:
- training/dataset/observational/fixtures/*/expected.json (investigate)
- training/dataset/observational/scripts/observational_runner.py (verify helpers)
- optionally training/dataset/observational/scripts/verify_investigate.py (new)

Commands:
  python3 -m py_compile training/dataset/observational/scripts/*.py
  python3 training/dataset/observational/scripts/ensure_pristine.py

Success checks:
- Investigate fixtures include expected.json
- A dry-run verifier returns fail on empty report and pass on a crafted correct report
- Claim-only path documented as legacy for old rows only

STOP if: verifier would require network; changing schema required fields incompatibly without updating validate_runs + sample.
```

## Claude computer use — differences

- Same scope; use terminal for py_compile and a couple of manual verifier dry-runs on investigate fixtures.
