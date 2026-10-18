# R3 interim status — 2026-10-18 10:15 a.m. ET

This is a time-stamped operations snapshot, **not** a completed experiment or
model-quality result. The complete frozen order contains 456 task packages.
At 2026-10-18 14:15:10 UTC, the Brev controller's `STATUS.json` reported
327 recorded receipts: 291 compatible and 36 incompatible, with 129 remaining.
The local journal had 328 newline-terminated lines (one header and 327
receipts), matching the status count. The controller was still running and
reported state `pulling`. The recorded journal-head SHA-256 was
`4d5c73bcc850f3fd276fdf0b845b3c9850c71ff60ee3ede0df8e20d4284a9962`.

The instance was healthy, with 100 GiB available on `/ephemeral`, and its
reported hourly rate was $3.96. The status explicitly recorded
`formal_model_outcomes_observed=false` and
`final_holdout_status=sealed_not_read_or_run`.

The partial counts cannot be used as a final compatibility rate or model
comparison. No qualification, v2 training, base/v1/v2 evaluation, or formal
N=144/288/432 look has occurred. The registered controller and terminal watcher
are left running. After all 456 receipts exist, the terminal watcher must
independently verify and package the complete matrix, hashes, and cost before
any final report replaces this interim snapshot. No incompatible package may
be silently dropped to create a smaller cohort.
