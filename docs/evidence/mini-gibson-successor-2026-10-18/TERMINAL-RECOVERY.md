# Terminal evidence recovery

R3 wrote all 456 immutable compatibility receipts and ended at
`preflight_complete_incompatible`. The independent terminal watcher failed
closed before packaging evidence because its root-owned Git command rejected
the ubuntu-owned source checkout as a dubious ownership boundary. It did not
change the journal, manifest, receipts, or source commit.

After a read-only cross-vendor review, we verified the exact source commit,
clean checkout, released controller and journal locks, absent output package,
and the original finalizer hash
`7bb3ce667b39613335ea837fd8698fe9035a12ad569bb76938c7d44fd75b51b6`.
We ran that unchanged finalizer once with Git's `safe.directory` setting scoped
to that one command and the exact remote source path. It independently
reconstructed the terminal manifest and confirmed the journal had not changed.
The final manifest SHA-256 is
`0c7ccd4784f334e20cbe0a5647d0c58391ebdcc25cf1229ffb4493cb9245b83a`;
the journal SHA-256 is
`2cf767139e2d021a4b7c0266572a6036bfd76b650b65858df19958c9ebd00298`.

The Brev file-copy command could not authenticate, though the already
authorized SSH connection worked. We transferred only the exact ten-file
public package over that connection, checked its inventory and lack of
symlinks, then verified every hash in `SHA256SUMS` and ran the public evidence
verifier. No private Docker config, credentials, image layers, model weights,
or raw environment dump was transferred or committed.

The 50 incompatibilities remain immutable. This recovery did not run tests,
models, agents, parsers, qualification, or training; the final holdout stayed
operationally sealed.
