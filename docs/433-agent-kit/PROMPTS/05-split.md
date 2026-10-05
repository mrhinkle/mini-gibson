# Prompt — Phase 5 DEV/TEST split

## Codex CLI

```text
Phase 5: create held-out TEST split by task_id for #433.

Scope:
- Run split_dataset.py on validated runs.jsonl
- Do not train/prompt-iterate on TEST tasks afterward
- splits/ is gitignored — tell Mark/John where files landed

Commands:
  python3 training/dataset/observational/scripts/split_dataset.py \
    --runs "$OBS_ROOT/runs.jsonl" \
    --out-dir "$OBS_ROOT/splits" \
    --test-fraction 0.2

Success checks:
- split_meta.json shows disjoint dev_tasks/test_tasks
- Row counts sum to total

STOP if: Mark/John have not frozen the salt/fraction; TEST would include tasks used for prompt hacking this week.
```

## Claude computer use — differences

- Same; show Mark/John the test_tasks list before any further collection that might touch those ids.
