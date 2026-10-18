# Successor experiment evidence

This directory records the preregistered successor to the stopped 2026-10-18
qualification experiment. See [PROTOCOL.md](PROTOCOL.md).

The proposed post-run Langfuse and Jev improvement loop is documented in
[CONTINUOUS-IMPROVEMENT.md](CONTINUOUS-IMPROVEMENT.md). It is intentionally
separate from the active compatibility preflight and cannot change scores or
unseal the final holdout.

The R3 compatibility preflight is processing the complete frozen 456-task order.
Its terminal journal, manifest, public-safe matrix, summary, cost record, and
plain-language report will be added here only after independent hash
verification of all 456 receipts. No new model conclusion is valid:
the preflight runs no model, agent, parser, or tests.

The [time-stamped interim status](INTERIM-STATUS.md) records progress without
turning partial receipts into a final result.

The project deliverable is the reproducible training and evaluation pipeline,
not a claim that this run produced a production-ready model. The successor
`REPORT.md` is pending. For the completed v1 conclusion, see the
[v1/v2 report](../mini-gibson-v2-2026-10-18/REPORT.md).

After the terminal successor package is added, verify it with:

```bash
python3 docs/evidence/mini-gibson-successor-2026-10-18/verify_evidence.py
```

The repository, model, dataset, holdout-source, and proposed-integration links
are indexed in the repository-wide [project map](../../PROJECT-MAP.md).

The first controller root stopped before its first task receipt on an
infrastructure-only archive ownership error. See [RECOVERY-R2.md](RECOVERY-R2.md)
for the preserved evidence and outcome-blind successor-root repair.

R2 then recorded two compatible tasks and stopped before task 3 because the
host precheck correctly rejected a gold patch that modifies a test-like path,
but the v1 compatibility schema could not serialize that precheck result. See
[RECOVERY-R3.md](RECOVERY-R3.md). R3 keeps every frozen task and records such
policy failures as immutable incompatibilities without launching a container.
