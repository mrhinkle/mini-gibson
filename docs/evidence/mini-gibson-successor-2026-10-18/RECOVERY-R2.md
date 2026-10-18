# Successor preflight recovery R2

The first successor controller root stopped before writing any task receipt.
Its journal contained only the invariant header; no candidate result was
observed, consumed, or reclassified.

The first immutable image pulled successfully. The verifier then returned its
sealed-payload extraction exit code 81. A bounded reproduction under the same
container identity and isolation flags showed that GNU `tar` extracted the
file but returned failure because it tried to restore archive UID/GID 1000.
The verifier ran as root with all capabilities removed, so it correctly lacked
`CAP_CHOWN`:

```text
tar: test-command: Cannot change ownership to uid 1000, gid 1000: Operation not permitted
tar_rc=2
```

This is evaluator infrastructure, not task compatibility. The generic repair
adds `tar --no-same-owner` to sealed-payload extraction. It does not change any
candidate, patch, test, parser, model, budget, or outcome rule. The failed root
is preserved at `/ephemeral/mini-gibson-successor-20261018`; its terminal state
reported zero recorded receipts and 456 remaining.

After tests and fresh cross-vendor review, the complete 456-task preflight will
restart under a new durable R2 root, source commit, journal header, and
controller identity. It will not modify or continue the failed root.
