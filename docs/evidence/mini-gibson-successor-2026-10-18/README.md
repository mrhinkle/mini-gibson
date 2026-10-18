# Successor experiment evidence

This directory records the preregistered successor to the stopped 2026-10-18
qualification experiment. See [PROTOCOL.md](PROTOCOL.md).

The proposed post-run Langfuse and Jev improvement loop is documented in
[CONTINUOUS-IMPROVEMENT.md](CONTINUOUS-IMPROVEMENT.md). It is intentionally
separate from the active compatibility preflight and cannot change scores or
unseal the final holdout.

The compatibility preflight is the next experiment. Its receipts and terminal
manifest will be added here from the durable Brev run after hash verification.
No model conclusion is valid at the preflight stage.

The first controller root stopped before its first task receipt on an
infrastructure-only archive ownership error. See [RECOVERY-R2.md](RECOVERY-R2.md)
for the preserved evidence and outcome-blind successor-root repair.

R2 then recorded two compatible tasks and stopped before task 3 because the
host precheck correctly rejected a gold patch that modifies a test-like path,
but the v1 compatibility schema could not serialize that precheck result. See
[RECOVERY-R3.md](RECOVERY-R3.md). R3 keeps every frozen task and records such
policy failures as immutable incompatibilities without launching a container.
