# Successor preflight recovery R3

R2 verified the archive-ownership repair and wrote two compatible receipts.
Before entering a container for task 3, the host verifier correctly rejected a
gold patch that modifies `src/components/box/box.spec.tsx`. Product patches may
not modify tests or hidden-verifier paths.

That rejection is a genuine, outcome-blind task compatibility result. The v1
compatibility receipt required two container-run records, however, so it could
not serialize a host precheck incompatibility. The controller stopped before
writing task 3. R2's two valid receipts and terminal status remain preserved at
`/ephemeral/mini-gibson-successor-r2-20261018`.

R3 advances the compatibility receipt schema to v2. A policy-invalid patch is
recorded once with a bounded, hash-bound `precheck_error`, `compatible: false`,
and no container runs. Infrastructure and integrity failures still stop without
a receipt. Successful and container-mechanics receipts retain the two-run
contract. The verifier continues to accept archived v1 receipts.

R3 restarts the complete frozen 456-task order under a new source commit,
journal header, and durable root. It does not exclude task 3, continue R2 at
task 3, or form a 455-plus-one cohort. Because at least one incompatibility is
already known, R3 is expected to produce an incompatible terminal matrix; no
qualification, training, or model conclusion may follow from this cohort.
