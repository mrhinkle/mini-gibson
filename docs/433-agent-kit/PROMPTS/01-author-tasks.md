# Prompt — Phase 1 Author tasks

## Codex CLI

```text
Phase 1: author/extend DEV_OBSERVATIONAL fixtures for #433.

Scope:
- Add harder synthetic tasks under training/dataset/observational/fixtures/ AND mirror into fixture_templates/
- Update training/dataset/observational/tasks.manifest.json
- Follow docs/433-agent-kit/EXPANSION.md conventions
- Never use holdout benchmarks

Files to touch:
- training/dataset/observational/fixtures/<task_id>/**
- training/dataset/observational/fixture_templates/<task_id>/**
- training/dataset/observational/tasks.manifest.json

Commands:
  python3 training/dataset/observational/scripts/ensure_pristine.py
  # for each new fix task, unittest should FAIL on pristine tree

Success checks:
- Manifest validates as JSON; every task has task_id, kind, path, verify_cmd, goal
- ensure_pristine exits 0
- Each fixture README states Split: DEV_OBSERVATIONAL

STOP if: task might be a holdout; you need production repo secrets; spend would be required (this phase is local-only).
```

## Claude computer use — differences

- Create fixtures via the file tools / editor; run `ensure_pristine.py` in terminal after batches of ~10 tasks.
- Keep diffs reviewable for Mark/John (small commits).
